"""Membership state changes (BACKEND_ARCHITECTURE.md section 8).

Turning a paid booking hold into the active membership (T14), then owner-assisted admission, renewal and
archival (T15). Writers take locks in the order Library, Seat, Membership, Payment, Hold (SPEC.md 4.1).
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.dates import business_today
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.libraries.models import PricingPlan
from apps.notifications import services as notifications

from . import selectors
from .models import Membership

logger = logging.getLogger("apps.memberships")

RENEWAL_OPENS_DAYS_BEFORE_DUE = 7  # BACKEND_ARCHITECTURE.md 6: RENEWAL_NOT_OPEN
ADMISSION_START_WINDOW_DAYS = 30  # #54: start_date within today -30 ... +30


def _accounts():
    """`accounts.services`, imported lazily (accounts never imports memberships at load time)."""
    from apps.accounts import services

    return services


def _payments():
    """`payments.services`, imported lazily because payments imports this module."""
    from apps.payments import services

    return services


def _attendance():
    """`attendance.services`, imported lazily (attendance imports memberships models)."""
    from apps.attendance import services

    return services


def _seats():
    """`seats.services`, imported lazily like the other cross-app writers."""
    from apps.seats import services

    return services


def activate_from_hold(*, hold, start_date: date) -> Membership:
    """Create the active online membership a verified payment pays for (SPEC.md 4.3, BOOK-06).

    The caller (payments.confirm_payment) already holds the seat row lock and has checked that the seat and
    the student are free, inside one transaction. If a race still slips through, the partial uniques
    (`membership_one_live_per_seat`, `membership_one_live_per_student_library`) raise IntegrityError and the
    caller treats the seat as lost.

    The period is the plan's duration from `start_date`; the amount and duration come from the plan row, never
    from the request.
    """
    plan = hold.plan
    membership = Membership.objects.create(
        student=hold.student,
        library=hold.library,
        seat=hold.seat,
        plan=plan,
        source=Membership.Source.ONLINE,
        state=Membership.State.ACTIVE,
        start_date=start_date,
        next_due_date=start_date + timedelta(days=plan.duration_days),
        created_by=hold.student,
    )
    audit.record(
        actor=hold.student,
        action="membership.create",
        entity_type="membership",
        entity_id=membership.pk,
        library=hold.library,
        changes={"seat": hold.seat.label, "plan": plan.name, "source": "online"},
    )
    logger.info(
        "Membership activated from hold",
        extra={"membership_id": str(membership.pk), "hold_id": str(hold.pk), "student_id": str(hold.student_id)},
    )
    return membership


# --- Shared renewal rules ------------------------------------------------------------------------------------


def lock_membership(membership_id, *, library=None, student=None) -> Membership:
    """Lock one membership (scoped to the owner's library or the student), or 404."""
    queryset = Membership.objects.select_for_update(of=("self",)).select_related("seat", "library", "plan", "student")
    if library is not None:
        queryset = queryset.filter(library=library)
    if student is not None:
        queryset = queryset.filter(student=student)
    try:
        return queryset.get(pk=membership_id)
    except (Membership.DoesNotExist, ValueError, TypeError):
        raise NotFound() from None


def require_active(membership: Membership) -> None:
    if membership.state != Membership.State.ACTIVE:
        raise Conflict("This membership has been archived.", code="MEMBERSHIP_ARCHIVED")


def require_renewable(membership: Membership, *, today: date) -> None:
    """Online renewal opens 7 days before the due date and stays open while overdue."""
    require_active(membership)
    if membership.next_due_date > today + timedelta(days=RENEWAL_OPENS_DAYS_BEFORE_DUE):
        raise Conflict("Renewal opens 7 days before your due date.", code="RENEWAL_NOT_OPEN")


def plan_for_renewal(membership: Membership, plan_id=None) -> PricingPlan:
    """The plan of the next period: the given one (same library) or the current one. Must be active."""
    if plan_id is None:
        plan = membership.plan
    else:
        plan = PricingPlan.objects.filter(pk=plan_id, library_id=membership.library_id).first()
        if plan is None:
            raise NotFound()
    if not plan.is_active:
        raise Conflict("This plan is no longer available. Please choose another.", code="PLAN_INACTIVE")
    return plan


def renewal_period(*, next_due_date: date, duration_days: int, today: date) -> tuple[date, date]:
    """Decision D5: the new period starts at the old due date, or today once more than 15 days overdue."""
    overdue_days = (today - next_due_date).days
    start = today if overdue_days > settings.RENEWAL_RESTART_AFTER_OVERDUE_DAYS else next_due_date
    return start, start + timedelta(days=duration_days)


def apply_renewal(*, membership: Membership, plan: PricingPlan, today: date, actor) -> tuple[date, date]:
    """Extend a *locked*, active membership by one period of `plan` and return (period_start, period_end).

    The seat is kept. The caller records the payment (online confirmation or `renew_offline`).
    """
    require_active(membership)
    period_start, period_end = renewal_period(
        next_due_date=membership.next_due_date, duration_days=plan.duration_days, today=today
    )
    changes = {"next_due_date": [str(membership.next_due_date), str(period_end)]}
    if membership.plan_id != plan.pk:
        changes["plan"] = [membership.plan.name, plan.name]
        membership.plan = plan
    membership.next_due_date = period_end
    membership.save(update_fields=["plan", "next_due_date", "updated_at"])
    audit.record(
        actor=actor,
        action="membership.renew",
        entity_type="membership",
        entity_id=membership.pk,
        library=membership.library,
        changes=changes,
    )
    return period_start, period_end


# --- Owner-recorded renewal (#48) ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RenewalResult:
    membership: Membership
    payment: object


@transaction.atomic
def renew_offline(*, library, owner, membership_id, method, plan_id=None, paid_at=None, notes="") -> RenewalResult:
    """The owner records an offline renewal payment for a member (#48, PAY-07, MEM-05)."""
    membership = lock_membership(membership_id, library=library)
    require_active(membership)
    plan = plan_for_renewal(membership, plan_id)
    period_start, period_end = apply_renewal(membership=membership, plan=plan, today=business_today(), actor=owner)
    payment = _payments().record_offline_payment(
        membership=membership,
        plan=plan,
        purpose="renewal",
        method=method,
        recorded_by=owner,
        period_start=period_start,
        period_end=period_end,
        paid_at=paid_at,
        notes=notes,
    )
    return RenewalResult(membership=membership, payment=payment)


# --- Owner-assisted admission (#54) --------------------------------------------------------------------------


@dataclass(frozen=True)
class AdmissionResult:
    student: object
    created: bool
    membership: Membership
    payment: object


@transaction.atomic
def admit_offline_student(
    *, library, owner, student: dict, seat_id, plan_id, start_date: date | None, payment: dict
) -> AdmissionResult:
    """Register a walk-in student, give them a seat and record their payment in one transaction (OFF-01/02).

    Locks the seat first (SPEC.md 4.1), so an admission and an online booking for one seat cannot both win.
    The identity follows the SPEC.md 4.6 table; a manual hold of this library on the seat is consumed.
    """
    today = business_today()
    start = start_date or today
    if abs((start - today).days) > ADMISSION_START_WINDOW_DAYS:
        raise ValidationFailed(details={"start_date": ["The start date must be within 30 days of today."]})
    plan = PricingPlan.objects.filter(pk=plan_id, library=library).first()
    if plan is None:
        raise NotFound()
    if not plan.is_active:
        raise Conflict("This plan is no longer available. Please choose another.", code="PLAN_INACTIVE")

    seat = _seats().lock_seat(seat_id, library=library)
    _seats().claim_seat_for_admission(seat, actor=owner)
    user, created = _accounts().admit_identity(
        name=student["name"],
        phone=student["phone"],
        email=student.get("email"),
        domain_code=student.get("domain_code"),
    )
    if selectors.student_is_member(user, library):
        raise Conflict("This student already has a membership at your library.", code="ALREADY_MEMBER")

    try:
        with transaction.atomic():
            membership = Membership.objects.create(
                student=user,
                library=library,
                seat=seat,
                plan=plan,
                source=Membership.Source.OFFLINE,
                state=Membership.State.ACTIVE,
                start_date=start,
                next_due_date=start + timedelta(days=plan.duration_days),
                created_by=owner,
            )
    except IntegrityError:
        raise Conflict("This seat is not free.", code="SEAT_UNAVAILABLE") from None
    audit.record(
        actor=owner,
        action="membership.create",
        entity_type="membership",
        entity_id=membership.pk,
        library=library,
        changes={"seat": seat.label, "plan": plan.name, "source": "offline", "student_created": created},
    )
    paid = _payments().record_offline_payment(
        membership=membership,
        plan=plan,
        purpose="new_membership",
        method=payment["method"],
        recorded_by=owner,
        period_start=membership.start_date,
        period_end=membership.next_due_date,
        paid_at=payment.get("paid_at"),
        notes=payment.get("notes", ""),
    )
    logger.info(
        "Offline admission completed",
        extra={"membership_id": str(membership.pk), "student_id": str(user.pk), "student_created": created},
    )
    return AdmissionResult(student=user, created=created, membership=membership, payment=paid)


# --- Admission pre-check (#53) ---


def lookup_admission_identity(*, library, phone: str, email: str | None):
    """Who an admission with this phone and email would link to, as (user or None, is_member_here).

    Read-only. Applies the SPEC.md 4.6 decision table, so a conflicting identity or an owner is a 409 here too.
    """
    user = _accounts().resolve_admission_identity(phone=phone, email=email)
    if user is None:
        return None, False
    return user, selectors.student_is_member(user, library)


# --- Owner claim code (#55, T06b) ---


def issue_claim_code(*, library, owner, student_id):
    """One-time claim code for a walk-in student who has (or had) a membership at this library (#55, OFF-04).

    A student with no membership here is a 404, so an owner cannot probe for accounts of other libraries. The
    account itself must still be an unclaimed offline record (else 409). The plain code is returned once.
    """
    membership = Membership.objects.select_related("student").filter(library=library, student_id=student_id).first()
    if membership is None:
        raise NotFound()
    from apps.accounts import claims

    return claims.issue_claim_code(student=membership.student, issued_by=owner)


# --- Archival (#52) ------------------------------------------------------------------------------------------


@transaction.atomic
def archive_membership(*, library, owner, membership_id, reason: str) -> Membership:
    """End a membership and free its seat; payments and history are untouched (#52, MEM-06, SPEC.md 4.4).

    Locks Seat then Membership. The seat stays on the row as history. An open attendance record of the student
    at this library is closed in the same transaction, and the student is notified (`membership_archived`,
    SPEC.md 3.13 and 4.5). The owner is not notified and the owner's reason is never put in the message.
    """
    seat_id = Membership.objects.filter(pk=membership_id, library=library).values_list("seat_id", flat=True).first()
    if seat_id is None:
        raise NotFound()
    _seats().lock_seat_by_pk(seat_id)
    membership = lock_membership(membership_id, library=library)
    require_active(membership)
    membership.state = Membership.State.ARCHIVED
    membership.archived_at = timezone.now()
    membership.archived_by = owner
    membership.archive_reason = reason.strip()
    membership.save(update_fields=["state", "archived_at", "archived_by", "archive_reason", "updated_at"])
    _attendance().close_for_membership(membership=membership, actor=owner)
    audit.record(
        actor=owner,
        action="membership.archive",
        entity_type="membership",
        entity_id=membership.pk,
        library=library,
        changes={"seat": membership.seat.label},
        reason=membership.archive_reason,
    )
    notifications.notify(
        recipient=membership.student,
        type="membership_archived",
        title="Your membership has ended",
        body=(
            f"{library.name} has ended your membership. Seat {membership.seat.label} is now free. "
            "Please contact the library if you think this is a mistake."
        ),
        dedup_key=f"membership:{membership.pk}:archived:{membership.student_id}",
        entity=("membership", membership.pk),
    )
    logger.info("Membership archived", extra={"membership_id": str(membership.pk), "owner_id": str(owner.pk)})
    return membership
