"""All seat state changes (BACKEND_ARCHITECTURE.md section 8, SPEC.md 3.8).

Views only parse, check permissions, call these and wrap the result.
Removing (#33) and disabling (#34) a seat both refuse a seat that has a non-archived
membership or a live hold (409 SEAT_IN_USE), decided under the seat lock.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.libraries import services as library_services
from apps.libraries.models import Library, PricingPlan

from .models import Seat, SeatHold

logger = logging.getLogger("apps.seats")

MAX_SEATS_PER_REQUEST = 500


@dataclass(frozen=True)
class SeatSpec:
    label: str
    row_label: str = ""
    position: int | None = None


def grid_specs(rows: list[str], seats_per_row: int) -> list[SeatSpec]:
    """Labels "{row}-{n}" (A-1, A-2 ...) with `row_label` and `position` set (#31 grid mode)."""
    return [
        SeatSpec(label=f"{row}-{n}", row_label=row, position=n) for row in rows for n in range(1, seats_per_row + 1)
    ]


def _locked_library(library: Library) -> Library:
    return Library.objects.select_for_update().get(pk=library.pk)


def _locked_seat(library: Library, seat: Seat) -> Seat:
    try:
        return Seat.objects.select_for_update().get(pk=seat.pk, library=library)
    except Seat.DoesNotExist as exc:
        raise NotFound() from exc


@transaction.atomic
def create_seats(*, library: Library, actor, specs: list[SeatSpec]) -> tuple[list[Seat], list[dict]]:
    """Add seats (#31). Existing active labels are skipped, never reset or duplicated.

    The Library row is locked, so two requests adding the same labels cannot both create them.
    Returns (created, skipped).
    """
    if not specs:
        raise ValidationFailed(details={"seats": ["Add at least one seat."]})
    if len(specs) > MAX_SEATS_PER_REQUEST:
        raise ValidationFailed(details={"seats": [f"Add at most {MAX_SEATS_PER_REQUEST} seats per request."]})
    library = _locked_library(library)

    taken = {
        label.lower() for label in Seat.objects.filter(library=library, is_active=True).values_list("label", flat=True)
    }
    to_create: list[Seat] = []
    skipped: list[dict] = []
    for spec in specs:
        label = spec.label.strip()
        if label.lower() in taken:
            skipped.append({"label": label, "reason": "exists"})
            continue
        taken.add(label.lower())
        to_create.append(Seat(library=library, label=label, row_label=spec.row_label.strip(), position=spec.position))
    created = Seat.objects.bulk_create(to_create)

    audit.record(
        actor=actor,
        action="seat.create_batch",
        entity_type="library",
        entity_id=library.pk,
        library=library,
        changes={"created": len(created), "skipped": len(skipped)},
    )
    library_services.refresh_publish_state(library)
    logger.info("Seats added", extra={"library_id": str(library.pk), "added": len(created), "skipped": len(skipped)})
    return created, skipped


@transaction.atomic
def update_seat(*, library: Library, seat: Seat, actor, data: dict) -> Seat:
    """Relabel or reposition a seat (#32). The label stays unique among active seats."""
    seat = _locked_seat(library, seat)
    before = {"label": seat.label, "row_label": seat.row_label, "position": seat.position}
    if "label" in data:
        label = data["label"].strip()
        clash = Seat.objects.filter(library=library, is_active=True, label__iexact=label).exclude(pk=seat.pk)
        if seat.is_active and clash.exists():
            raise Conflict("A seat with this label already exists in your library.")
        seat.label = label
    if "row_label" in data:
        seat.row_label = data["row_label"].strip()
    if "position" in data:
        seat.position = data["position"]
    seat.save()
    audit.record(
        actor=actor,
        action="seat.update",
        entity_type="seat",
        entity_id=seat.pk,
        library=library,
        changes=audit.changes_between(
            before, {"label": seat.label, "row_label": seat.row_label, "position": seat.position}
        ),
    )
    return seat


@transaction.atomic
def enable_seat(*, library: Library, seat: Seat, actor) -> Seat:
    """End maintenance on a seat (#35). Idempotent."""
    seat = _locked_seat(library, seat)
    if seat.is_disabled:
        seat.is_disabled = False
        seat.disabled_reason = ""
        seat.save(update_fields=["is_disabled", "disabled_reason", "updated_at"])
        audit.record(actor=actor, action="seat.enable", entity_type="seat", entity_id=seat.pk, library=library)
    return seat


# --- Holds (T12, BOOK-01..05, SEAT-07) ---------------------------------------------------------
#
# Locking order (BACKEND_ARCHITECTURE.md 8.1): Library -> Seat -> ... -> Hold. Every writer of a hold
# locks the seat row first, so the seat is the mutex for everything that can happen to that seat.
# Not here, by design: the pending Payment of a cancelled hold (T14), the student notification when an
# owner releases a hold (T13 is not on this branch and SPEC.md 3.13 defines no type for it), and the
# scheduled `expire_holds` step wiring (T24 calls `expire_dead_holds`).


def _memberships():
    """`memberships.selectors`, imported lazily so `seats` never imports memberships models at load time."""
    from apps.memberships import selectors

    return selectors


def _payments():
    """`payments.services`, imported lazily because payments imports seats (no import cycle at load time)."""
    from apps.payments import services

    return services


def _locked_seat_by_id(seat_id, *, library: Library | None = None) -> Seat:
    queryset = Seat.objects.select_for_update().select_related("library").filter(is_active=True)
    if library is not None:
        queryset = queryset.filter(library=library)
    try:
        return queryset.get(pk=seat_id)
    except (Seat.DoesNotExist, ValueError, TypeError, DjangoValidationError) as exc:
        raise NotFound() from exc


def expire_dead_holds_for_seat(seat: Seat, *, now=None) -> int:
    now = now or timezone.now()
    return SeatHold.objects.filter(seat=seat, status=SeatHold.Status.PENDING, expires_at__lte=now).update(
        status=SeatHold.Status.EXPIRED, closed_at=now, updated_at=now
    )


def expire_dead_holds_for_student(student, library: Library, *, now=None) -> int:
    now = now or timezone.now()
    return SeatHold.objects.filter(
        student=student,
        library=library,
        kind=SeatHold.Kind.BOOKING,
        status=SeatHold.Status.PENDING,
        expires_at__lte=now,
    ).update(status=SeatHold.Status.EXPIRED, closed_at=now, updated_at=now)


def expire_dead_holds(*, now=None) -> int:
    """The `expire_holds` job step: pending booking holds past `expires_at` become `expired`.

    Reads never depend on it (a dead hold is already treated as free), it only tidies the table.
    Idempotent: a row that is no longer pending is not touched.
    """
    now = now or timezone.now()
    count = SeatHold.objects.filter(status=SeatHold.Status.PENDING, expires_at__lte=now).update(
        status=SeatHold.Status.EXPIRED, closed_at=now, updated_at=now
    )
    if count:
        audit.record(
            actor=None,
            action="hold.expired_batch",
            entity_type="seat_hold",
            entity_id=uuid.uuid4(),
            changes={"expired": count},
        )
        logger.info("Expired dead holds", extra={"expired": count})
    return count


def _conflict(message: str, code: str, **context) -> Conflict:
    logger.warning("Seat booking conflict detected", extra={"error_code": code, **context})
    return Conflict(message, code=code)


@transaction.atomic
def create_booking_hold(*, student, seat_id, plan_id) -> SeatHold:
    """Hold a seat for `SEAT_HOLD_MINUTES` for a student who is about to pay (#38, BACKEND_ARCHITECTURE.md 8.2).

    The seat row lock plus `seathold_one_pending_per_seat` give exactly one winner when N students race.
    """
    seat = _locked_seat_by_id(seat_id)
    library = seat.library
    ctx = {"seat_id": str(seat.pk), "student_id": str(student.pk)}
    if not (library.is_active and library.is_published):
        raise _conflict("This library isn't taking bookings right now.", "LIBRARY_NOT_BOOKABLE", **ctx)
    plan = PricingPlan.objects.filter(pk=plan_id, library=library, is_active=True).first() if plan_id else None
    if plan is None:
        raise _conflict("This plan is no longer available. Please choose another.", "PLAN_INACTIVE", **ctx)
    unavailable = "That seat was just taken. Please pick another."
    if seat.is_disabled:
        raise _conflict(unavailable, "SEAT_UNAVAILABLE", **ctx)

    now = timezone.now()
    expire_dead_holds_for_seat(seat, now=now)
    memberships = _memberships()
    if memberships.active_membership_exists(seat):
        raise _conflict(unavailable, "SEAT_UNAVAILABLE", **ctx)
    if memberships.student_is_member(student, library):
        raise _conflict("You already have a seat at this library.", "ALREADY_MEMBER", **ctx)
    if SeatHold.objects.live(now).filter(seat=seat).exists():
        raise _conflict(unavailable, "SEAT_UNAVAILABLE", **ctx)
    expire_dead_holds_for_student(student, library, now=now)
    if SeatHold.objects.live(now).filter(student=student, library=library, kind=SeatHold.Kind.BOOKING).exists():
        raise _conflict("You already have a seat on hold at this library.", "HOLD_EXISTS", **ctx)

    hold = SeatHold.objects.create(
        seat=seat,
        library=library,
        kind=SeatHold.Kind.BOOKING,
        student=student,
        plan=plan,
        created_by=student,
        expires_at=now + timedelta(minutes=settings.SEAT_HOLD_MINUTES),
    )
    audit.record(
        actor=student,
        action="hold.create",
        entity_type="seat_hold",
        entity_id=hold.pk,
        library=library,
        changes={"seat": seat.label, "plan": plan.name},
    )
    logger.info("Seat hold created", extra={"hold_id": str(hold.pk), **ctx})
    return hold


def _own_pending_hold_for_update(*, hold: SeatHold) -> SeatHold:
    """Lock the hold's seat first, then re-read the hold under the lock (Seat -> Hold order)."""
    Seat.objects.select_for_update().get(pk=hold.seat_id)
    return SeatHold.objects.select_for_update().get(pk=hold.pk)


HOLD_NOT_ACTIVE = "This seat hold is no longer active."


def _is_live_pending(hold: SeatHold, *, now) -> bool:
    """True if the hold is still pending and not past its expiry. A pending hold that is already dead is
    closed as `expired` here, so the caller must raise *after* the transaction commits or the tidy-up is lost."""
    if hold.status == SeatHold.Status.PENDING and hold.expires_at is not None and hold.expires_at <= now:
        hold.status = SeatHold.Status.EXPIRED
        hold.closed_at = now
        hold.save(update_fields=["status", "closed_at", "updated_at"])
    return hold.status == SeatHold.Status.PENDING


def cancel_hold(*, student, hold: SeatHold) -> SeatHold:
    """The student abandons their own pending booking hold (#40, BOOK-04). The seat is free again at once."""
    cancelled = _cancel_hold(student=student, hold=hold)
    if cancelled is None:
        raise Conflict(HOLD_NOT_ACTIVE, code="HOLD_EXPIRED")
    return cancelled


@transaction.atomic
def _cancel_hold(*, student, hold: SeatHold) -> SeatHold | None:
    now = timezone.now()
    payments = _payments()
    pending = payments.lock_pending_for_hold(hold.pk)  # Payment before Seat, as confirm_payment does
    hold = _own_pending_hold_for_update(hold=hold)
    if hold.student_id != student.pk or hold.kind != SeatHold.Kind.BOOKING:
        raise NotFound()
    if not _is_live_pending(hold, now=now):
        return None
    hold.status = SeatHold.Status.CANCELLED
    hold.closed_at = now
    hold.save(update_fields=["status", "closed_at", "updated_at"])
    payments.cancel_locked(pending)  # #40: any pending Payment for the hold becomes cancelled
    audit.record(actor=student, action="hold.cancel", entity_type="seat_hold", entity_id=hold.pk, library=hold.library)
    logger.info("Seat hold cancelled", extra={"hold_id": str(hold.pk), "student_id": str(student.pk)})
    return hold


@transaction.atomic
def place_manual_hold(*, library: Library, seat_id, actor, reason: str) -> SeatHold:
    """Block a free seat of the owner's library for an offline or physical reason (#36, SEAT-07). No expiry."""
    seat = _locked_seat_by_id(seat_id, library=library)
    now = timezone.now()
    expire_dead_holds_for_seat(seat, now=now)
    if (
        seat.is_disabled
        or _memberships().active_membership_exists(seat)
        or SeatHold.objects.live(now).filter(seat=seat).exists()
    ):
        raise _conflict("This seat is not free.", "SEAT_UNAVAILABLE", seat_id=str(seat.pk), actor_id=str(actor.pk))
    hold = SeatHold.objects.create(
        seat=seat,
        library=library,
        kind=SeatHold.Kind.OWNER_MANUAL,
        reason=reason.strip(),
        created_by=actor,
    )
    audit.record(
        actor=actor,
        action="hold.manual_place",
        entity_type="seat_hold",
        entity_id=hold.pk,
        library=library,
        changes={"seat": seat.label},
        reason=hold.reason,
    )
    logger.info("Manual seat hold placed", extra={"hold_id": str(hold.pk), "seat_id": str(seat.pk)})
    return hold


def release_hold(*, library: Library, hold: SeatHold, actor, reason: str) -> SeatHold:
    """The owner frees any pending hold of their library, a stuck student hold or a manual one (#37, SEAT-07).

    Only a pending hold can be released. A paid membership is never touched: payment completes a hold
    into a membership, and a completed hold is no longer pending.
    """
    released = _release_hold(library=library, hold=hold, actor=actor, reason=reason)
    if released is None:
        raise Conflict(HOLD_NOT_ACTIVE, code="HOLD_EXPIRED")
    return released


@transaction.atomic
def _release_hold(*, library: Library, hold: SeatHold, actor, reason: str) -> SeatHold | None:
    now = timezone.now()
    hold = _own_pending_hold_for_update(hold=hold)
    if hold.library_id != library.pk:
        raise NotFound()
    if not _is_live_pending(hold, now=now):
        return None
    hold.status = SeatHold.Status.RELEASED
    hold.closed_at = now
    hold.save(update_fields=["status", "closed_at", "updated_at"])
    audit.record(
        actor=actor,
        action="hold.release",
        entity_type="seat_hold",
        entity_id=hold.pk,
        library=library,
        changes={"kind": hold.kind},
        reason=reason.strip(),
    )
    logger.info("Seat hold released", extra={"hold_id": str(hold.pk), "actor_id": str(actor.pk)})
    return hold


def _in_use(seat: Seat, *, now) -> bool:
    """A non-archived membership or a live hold: the seat cannot be removed or taken out of service."""
    expire_dead_holds_for_seat(seat, now=now)
    return _memberships().active_membership_exists(seat) or SeatHold.objects.live(now).filter(seat=seat).exists()


@transaction.atomic
def deactivate_seat(*, library: Library, seat: Seat, actor, reason: str) -> Seat:
    """Remove a seat softly (#33, SEAT-02). The row, its holds and its memberships are kept as history.

    Refused while the seat has a non-archived membership or a live hold. Idempotent for a removed seat.
    """
    seat = _locked_seat(library, seat)
    if not seat.is_active:
        return seat
    if _in_use(seat, now=timezone.now()):
        raise Conflict("This seat has an active member or hold. Archive or release it first.", code="SEAT_IN_USE")
    seat.is_active = False
    seat.is_disabled = False  # a removed seat is not "in maintenance" (seat_disabled_is_active)
    seat.disabled_reason = ""
    seat.save(update_fields=["is_active", "is_disabled", "disabled_reason", "updated_at"])
    audit.record(
        actor=actor,
        action="seat.deactivate",
        entity_type="seat",
        entity_id=seat.pk,
        library=library,
        changes={"label": seat.label},
        reason=reason.strip(),
    )
    library_services.refresh_publish_state(library)
    logger.info("Seat removed", extra={"seat_id": str(seat.pk)})
    return seat


@transaction.atomic
def disable_seat(*, library: Library, seat: Seat, actor, reason: str) -> Seat:
    """Take a seat out of service for maintenance (#34, SEAT-04). Same guard as removal. Idempotent."""
    seat = _locked_seat(library, seat)
    if not seat.is_active:
        raise NotFound()
    if seat.is_disabled:
        return seat
    if _in_use(seat, now=timezone.now()):
        raise Conflict("This seat has an active member or hold. Archive or release it first.", code="SEAT_IN_USE")
    seat.is_disabled = True
    seat.disabled_reason = reason.strip()
    seat.save(update_fields=["is_disabled", "disabled_reason", "updated_at"])
    audit.record(
        actor=actor,
        action="seat.disable",
        entity_type="seat",
        entity_id=seat.pk,
        library=library,
        changes={"label": seat.label},
        reason=seat.disabled_reason,
    )
    return seat


def lock_seat(seat_id, *, library: Library) -> Seat:
    """Lock one active seat of the library for a writer in another app (the Seat step of SPEC.md 4.1).

    Unknown, inactive or foreign seats are a 404. Call inside `transaction.atomic()`.
    """
    return _locked_seat_by_id(seat_id, library=library)


def claim_seat_for_admission(seat: Seat, *, actor, now=None) -> None:
    """Check that a *locked* seat can be given to a walk-in student, consuming the owner's manual hold (OFF-02).

    Free means: not disabled, no active membership, no live student hold. A live manual hold of this library
    is the owner's own reservation, so it is completed (consumed) instead of blocking. Raises 409
    `SEAT_UNAVAILABLE` otherwise.
    """
    now = now or timezone.now()
    expire_dead_holds_for_seat(seat, now=now)
    if seat.is_disabled or _memberships().active_membership_exists(seat):
        raise _conflict("This seat is not free.", "SEAT_UNAVAILABLE", seat_id=str(seat.pk), actor_id=str(actor.pk))
    live = list(SeatHold.objects.live(now).filter(seat=seat).select_for_update())
    if any(hold.kind != SeatHold.Kind.OWNER_MANUAL for hold in live):
        raise _conflict("This seat is not free.", "SEAT_UNAVAILABLE", seat_id=str(seat.pk), actor_id=str(actor.pk))
    for hold in live:
        hold.status = SeatHold.Status.COMPLETED
        hold.closed_at = now
        hold.save(update_fields=["status", "closed_at", "updated_at"])
        audit.record(
            actor=actor,
            action="hold.consume",
            entity_type="seat_hold",
            entity_id=hold.pk,
            library=seat.library,
            changes={"seat": seat.label},
            reason="Consumed by an offline admission",
        )


def lock_seat_by_pk(seat_pk) -> Seat:
    """Lock a seat by id even if it is now inactive (archival must free a seat that was deactivated later)."""
    return Seat.objects.select_for_update().get(pk=seat_pk)
