"""Direct UPI payments with manual owner approval (SPEC.md 3.11b-c and 4.3b, FEATURES.md UPI-01 to UPI-12).

The student pays the library owner's own UPI account. LibraryHive never touches the money and cannot see whether
it arrived: the owner checks their UPI or bank history and approves or rejects. So a `UpiPaymentRequest` is only
a *claim*. The immutable `Payment` ledger gets a row only inside `approve_request`, through the same
`record_offline_payment` the owner's walk-in admission uses (method `upi_direct`, `verified_via=manual`,
`recorded_by=the approving owner`), so receipts, reports and the existing constraints all keep working.

Seat rule: the 15-minute booking hold is never extended. A pending request holds nothing; if the seat is gone
when the owner approves, nothing is activated and the owner chooses another free seat or rejects and refunds the
student directly (LibraryHive does not move money back).

Locking order (BACKEND_ARCHITECTURE.md 8.1): Request, then Seat, then Hold for a new membership; Request, then
Membership for a renewal. `seats.cancel_hold` takes Payment, Seat, Hold and never a Request, so there is no cycle.
"""

import logging
import re
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core import audit
from apps.core.dates import business_today
from apps.core.exceptions import Conflict, NotFound, ValidationFailed, lookup_constraint_error
from apps.core.images import process_upload
from apps.core.storage import private_storage, save_bytes
from apps.memberships import selectors as membership_selectors
from apps.memberships import services as membership_services
from apps.memberships.models import Membership
from apps.notifications import services as notifications
from apps.seats import services as seat_services
from apps.seats.models import Seat, SeatHold

from . import services as payment_services
from .models import LibraryPaymentSettings, Payment, UpiPaymentRequest

logger = logging.getLogger("apps.payments")

UTR_PATTERN = re.compile(r"^[A-Z0-9]{10,30}$")
UPI_ID_PATTERN = re.compile(r"^[A-Za-z0-9._\-]{2,64}@[A-Za-z][A-Za-z0-9]{1,31}$")

SEAT_UNAVAILABLE_MESSAGE = (
    "This seat is no longer free, so no membership was created. Approve the payment onto another free seat, "
    "or reject it and refund the student directly: LibraryHive cannot refund UPI transfers."
)


# --- Validation helpers ---------------------------------------------------------------------------------------


def normalise_utr(raw: str) -> str:
    """Upper case with every space removed, then 10 to 30 letters and digits (UPI references are 12 digits,
    some apps show a longer alphanumeric one)."""
    utr = re.sub(r"\s+", "", raw or "").upper()
    if not UTR_PATTERN.match(utr):
        raise ValidationFailed(
            details={"utr": ["Enter the transaction reference (UTR) exactly as your UPI app shows it."]}
        )
    return utr


def _delete_quietly(key: str) -> None:
    try:
        private_storage().delete(key)
    except Exception:
        logger.warning("Could not delete a private file", extra={"key_prefix": key.split("/")[0]})


# --- Library payment settings (owner) -------------------------------------------------------------------------


def _locked_settings(library) -> LibraryPaymentSettings:
    LibraryPaymentSettings.objects.get_or_create(library=library)
    return LibraryPaymentSettings.objects.select_for_update().get(library=library)


def update_settings(*, library, actor, data: dict) -> LibraryPaymentSettings:
    """Change the UPI ID, the instructions or the on/off switch. UPI payments need a QR or a UPI ID to be on."""
    with transaction.atomic():
        row = _locked_settings(library)
        changes: dict = {}
        if "upi_id" in data:
            upi_id = (data["upi_id"] or "").strip()
            if upi_id and not UPI_ID_PATTERN.match(upi_id):
                raise ValidationFailed(details={"upi_id": ["Enter a valid UPI ID, for example name@bank."]})
            if upi_id != row.upi_id:
                changes["upi_id"] = [row.upi_id, upi_id]
                row.upi_id = upi_id
        if "instructions" in data:
            instructions = (data["instructions"] or "").strip()
            if instructions != row.instructions:
                changes["instructions_changed"] = True
                row.instructions = instructions
        if "upi_enabled" in data and bool(data["upi_enabled"]) != row.upi_enabled:
            changes["upi_enabled"] = [row.upi_enabled, bool(data["upi_enabled"])]
            row.upi_enabled = bool(data["upi_enabled"])
        if row.upi_enabled and not (row.upi_id or row.qr_key):
            raise ValidationFailed(details={"upi_enabled": ["Upload your QR code or enter your UPI ID first."]})
        if changes:
            row.save()
            audit.record(
                actor=actor,
                action="payment_settings.update",
                entity_type="library_payment_settings",
                entity_id=row.pk,
                library=library,
                changes=changes,
            )
    return row


def set_qr(*, library, actor, uploaded_file) -> LibraryPaymentSettings:
    """Verify, re-encode (lossless, so it still scans) and store the QR in the private store; replaces any old one."""
    processed = process_upload(uploaded_file, qr=True)  # FILE_TYPE / FILE_TOO_LARGE before any state changes
    storage = private_storage()
    key = save_bytes(storage, f"payments/{library.pk}/qr/{uuid.uuid4().hex}.webp", processed.display)
    try:
        with transaction.atomic():
            row = _locked_settings(library)
            previous = row.qr_key
            row.qr_key = key
            row.save(update_fields=["qr_key", "updated_at"])
            audit.record(
                actor=actor,
                action="payment_settings.qr_replace" if previous else "payment_settings.qr_upload",
                entity_type="library_payment_settings",
                entity_id=row.pk,
                library=library,
                changes={"replaced": bool(previous)},
            )
    except Exception:
        _delete_quietly(key)
        raise
    if previous:
        _delete_quietly(previous)
    return row


def remove_qr(*, library, actor) -> LibraryPaymentSettings:
    with transaction.atomic():
        row = _locked_settings(library)
        if not row.qr_key:
            return row
        if row.upi_enabled and not row.upi_id:
            raise Conflict("Turn UPI payments off or add a UPI ID before removing the QR code.", code="QR_REQUIRED")
        previous, row.qr_key = row.qr_key, ""
        row.save(update_fields=["qr_key", "updated_at"])
        audit.record(
            actor=actor,
            action="payment_settings.qr_remove",
            entity_type="library_payment_settings",
            entity_id=row.pk,
            library=library,
        )
    _delete_quietly(previous)
    return row


# --- Student: submit and cancel -------------------------------------------------------------------------------


def submit_request(
    *, student, hold_id=None, membership_id=None, plan_id=None, utr: str, note: str = "", screenshot=None
) -> UpiPaymentRequest:
    """Record the student's claim that they paid the library by UPI. Confirms nothing.

    Library, plan, seat and amount come from the database (the student's own hold or membership), never from the
    request. A booking request is accepted while the student's own hold is live or has just lapsed (they may have
    paid and then run out of time); the seat is not reserved by it and is checked again at approval.
    """
    utr = normalise_utr(utr)
    note = (note or "").strip()
    today = business_today()
    hold = membership = None
    if hold_id is not None:
        hold = (
            SeatHold.objects.select_related("seat", "library", "plan")
            .filter(pk=hold_id, student=student, kind=SeatHold.Kind.BOOKING)
            .first()
        )
        if hold is None:
            raise NotFound()
        if hold.status not in (SeatHold.Status.PENDING, SeatHold.Status.EXPIRED):
            raise Conflict("This booking is no longer open. Please start again.", code="HOLD_CLOSED")
        library, plan, purpose = hold.library, hold.plan, Payment.Purpose.NEW_MEMBERSHIP
        if not plan.is_active:
            raise Conflict("This plan is no longer available. Please choose another.", code="PLAN_INACTIVE")
        if membership_selectors.student_is_member(student, library):
            raise Conflict("You already have a seat at this library.", code="ALREADY_MEMBER")
    else:
        membership = (
            Membership.objects.select_related("library", "plan", "seat")
            .filter(pk=membership_id, student=student)
            .first()
        )
        if membership is None:
            raise NotFound()
        plan = membership_services.plan_for_renewal(membership, plan_id)
        membership_services.require_renewable(membership, today=today)
        library, purpose = membership.library, Payment.Purpose.RENEWAL

    settings_row = LibraryPaymentSettings.objects.filter(library=library).first()
    if settings_row is None or not settings_row.upi_enabled:
        raise Conflict("This library is not taking UPI payments right now.", code="UPI_DISABLED")

    screenshot_key = ""
    if screenshot is not None:
        processed = process_upload(screenshot)
        screenshot_key = save_bytes(
            private_storage(), f"payments/{library.pk}/screenshots/{uuid.uuid4().hex}.webp", processed.display
        )
    try:
        with transaction.atomic():
            # Serialise two submissions for the same hold or membership; the partial uniques are the last guard.
            if hold is not None:
                SeatHold.objects.select_for_update().get(pk=hold.pk)
            else:
                locked = Membership.objects.select_for_update().get(pk=membership.pk)
                membership_services.require_renewable(locked, today=today)
            live = [UpiPaymentRequest.Status.PENDING, UpiPaymentRequest.Status.APPROVED]
            # A pending or approved UTR is taken by anyone. A rejected or cancelled one may be sent again by the
            # student who sent it (the owner may have rejected by mistake) but not claimed by someone else.
            if UpiPaymentRequest.objects.filter(utr=utr).filter(Q(status__in=live) | ~Q(student=student)).exists():
                raise Conflict(
                    "This UTR has already been submitted. Check the number, or contact the library.",
                    code="DUPLICATE_UTR",
                )
            request = UpiPaymentRequest.objects.create(
                library=library,
                student=student,
                plan=plan,
                purpose=purpose,
                hold=hold,
                seat=hold.seat if hold else None,
                membership=membership,
                amount=plan.price,
                utr=utr,
                student_note=note,
                screenshot_key=screenshot_key,
            )
            audit.record(
                actor=student,
                action="upi_payment.submit",
                entity_type="upi_payment_request",
                entity_id=request.pk,
                library=library,
                changes={"purpose": purpose, "amount": str(request.amount), "has_screenshot": bool(screenshot_key)},
            )
            notifications.notify(
                recipient=library.owner,
                type="upi_payment_submitted",
                title="UPI payment to check",
                body=(
                    f"{student.name} says they paid {request.amount} (UTR {utr}). "
                    "Check your UPI or bank history, then approve or reject the request."
                ),
                dedup_key=f"upi:{request.pk}:submitted:{library.owner_id}",
                entity=("upi_payment_request", request.pk),
            )
    except Exception as exc:
        if screenshot_key:
            _delete_quietly(screenshot_key)
        if isinstance(exc, IntegrityError):
            # A race that slipped past the checks above: the partial uniques decide, and the loser gets a clean 409.
            diag = getattr(getattr(exc, "__cause__", None), "diag", None)
            mapped = lookup_constraint_error(getattr(diag, "constraint_name", None))
            if mapped:
                raise Conflict(mapped[2], code=mapped[1]) from None
        raise
    logger.info(
        "UPI payment request submitted",
        extra={"request_id": str(request.pk), "student_id": str(student.pk), "library_id": str(library.pk)},
    )
    return request


def cancel_request(*, student, request_id) -> UpiPaymentRequest:
    """The student withdraws their own pending request. Nothing was activated, so nothing is undone."""
    with transaction.atomic():
        request = UpiPaymentRequest.objects.select_for_update().filter(pk=request_id, student=student).first()
        if request is None:
            raise NotFound()
        if request.status != UpiPaymentRequest.Status.PENDING:
            raise Conflict(f"This request was already {request.status}.", code="ALREADY_DECIDED")
        request.status = UpiPaymentRequest.Status.CANCELLED
        request.save(update_fields=["status", "updated_at"])
        audit.record(
            actor=student,
            action="upi_payment.cancel",
            entity_type="upi_payment_request",
            entity_id=request.pk,
            library=request.library,
        )
    return request


# --- Owner: approve and reject --------------------------------------------------------------------------------


def _lock_pending(library, request_id) -> UpiPaymentRequest:
    """Lock one request of the owner's library (404 for any other library) and require it to be pending."""
    request = (
        UpiPaymentRequest.objects.select_for_update(of=("self",))
        .select_related("student", "plan", "library__owner", "seat", "membership")
        .filter(pk=request_id, library=library)
        .first()
    )
    if request is None:
        raise NotFound()
    if request.status != UpiPaymentRequest.Status.PENDING:
        raise Conflict(f"This request was already {request.status}.", code="ALREADY_DECIDED")
    return request


def reject_request(*, library, owner, request_id, reason: str) -> UpiPaymentRequest:
    """Reject: nothing is activated and no `Payment` is written. The student is told, with the owner's reason."""
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise ValidationFailed(details={"reason": ["Tell the student why, in at least 3 characters."]})
    with transaction.atomic():
        request = _lock_pending(library, request_id)
        request.status = UpiPaymentRequest.Status.REJECTED
        request.reviewed_by = owner
        request.reviewed_at = timezone.now()
        request.review_note = reason[:300]
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
        audit.record(
            actor=owner,
            action="upi_payment.reject",
            entity_type="upi_payment_request",
            entity_id=request.pk,
            library=library,
            reason=reason[:300],
        )
        notifications.notify(
            recipient=request.student,
            type="upi_payment_rejected",
            title="Payment not confirmed",
            body=(
                f"{library.name} could not confirm your payment of {request.amount}. Reason: {request.review_note} "
                "If you did pay, contact the library directly: LibraryHive does not refund UPI transfers."
            ),
            dedup_key=f"upi:{request.pk}:rejected:{request.student_id}",
            entity=("upi_payment_request", request.pk),
        )
    logger.info("UPI payment request rejected", extra={"request_id": str(request.pk), "owner_id": str(owner.pk)})
    return request


def _seat_is_free(seat: Seat, student, *, now) -> bool:
    """The seat can go to this student: usable, not occupied, and no one else's live hold on it."""
    if not seat.is_active or seat.is_disabled:
        return False
    if membership_selectors.active_membership_exists(seat):
        return False
    return not SeatHold.objects.live(now).filter(seat=seat).exclude(student=student).exists()


def _activate_new(request: UpiPaymentRequest, owner, seat_id, *, now, today):
    library, student = request.library, request.student
    if membership_selectors.student_is_member(student, library):
        raise Conflict(
            "This student already has a seat at your library. Reject the request and refund them directly.",
            code="ALREADY_MEMBER",
        )
    seat = Seat.objects.select_for_update().filter(pk=seat_id or request.seat_id, library=library).first()
    if seat is None:
        raise NotFound()
    seat_services.expire_dead_holds_for_seat(seat, now=now)
    own_holds = list(
        SeatHold.objects.select_for_update().filter(
            student=student, library=library, kind=SeatHold.Kind.BOOKING, status=SeatHold.Status.PENDING
        )
    )
    if not _seat_is_free(seat, student, now=now):
        logger.warning(
            "UPI approval blocked: seat unavailable",
            extra={"request_id": str(request.pk), "seat_id": str(seat.pk), "student_id": str(student.pk)},
        )
        raise Conflict(SEAT_UNAVAILABLE_MESSAGE, code="SEAT_UNAVAILABLE")
    for hold in own_holds:
        hold.status = SeatHold.Status.COMPLETED
        hold.closed_at = now
        hold.save(update_fields=["status", "closed_at", "updated_at"])
    try:
        with transaction.atomic():
            membership = membership_services.activate_for_manual_payment(
                student=student, library=library, seat=seat, plan=request.plan, start_date=today, owner=owner
            )
    except IntegrityError:
        raise Conflict(SEAT_UNAVAILABLE_MESSAGE, code="SEAT_UNAVAILABLE") from None
    return membership, seat


def _renew(request: UpiPaymentRequest, owner, *, today):
    membership = (
        Membership.objects.select_for_update(of=("self",))
        .select_related("seat", "library", "plan", "student")
        .get(pk=request.membership_id)
    )
    if membership.state != Membership.State.ACTIVE:
        raise Conflict(
            "This membership has ended, so it cannot be renewed. Reject the request and refund the student directly.",
            code="MEMBERSHIP_ARCHIVED",
        )
    period_start, period_end = membership_services.apply_renewal(
        membership=membership, plan=request.plan, today=today, actor=owner
    )
    return membership, period_start, period_end


def approve_request(*, library, owner, request_id, seat_id=None) -> UpiPaymentRequest:
    """Approve after the owner has checked their own UPI or bank history. One transaction does everything.

    Re-checks the seat (new membership) or that the membership is still active (renewal) under the row locks,
    activates or extends the membership, writes the `Payment` ledger row and notifies the student. If the seat is
    gone it raises 409 `SEAT_UNAVAILABLE` and changes nothing; `seat_id` lets the owner approve onto another free
    seat of the same library. A second approval of the same request gets 409 `ALREADY_DECIDED`.
    """
    now, today = timezone.now(), business_today()
    with transaction.atomic():
        request = _lock_pending(library, request_id)
        if request.purpose == Payment.Purpose.NEW_MEMBERSHIP:
            membership, seat = _activate_new(request, owner, seat_id, now=now, today=today)
            period_start, period_end = membership.start_date, membership.next_due_date
            seat_label = seat.label
            summary = f"Seat {seat_label} at {library.name} is yours until {membership.next_due_date:%d %b %Y}."
        else:
            membership, period_start, period_end = _renew(request, owner, today=today)
            seat_label = membership.seat.label
            summary = f"Your membership at {library.name} is renewed until {membership.next_due_date:%d %b %Y}."
        payment = payment_services.record_offline_payment(
            membership=membership,
            plan=request.plan,
            purpose=request.purpose,
            method=Payment.Method.UPI_DIRECT,
            recorded_by=owner,
            period_start=period_start,
            period_end=period_end,
            notes=f"UPI request {request.pk}, UTR {request.utr}",
            notify=False,  # the `upi_payment_approved` message below is the one notification
        )
        request.status = UpiPaymentRequest.Status.APPROVED
        request.reviewed_by = owner
        request.reviewed_at = now
        request.payment = payment
        request.save(update_fields=["status", "reviewed_by", "reviewed_at", "payment", "updated_at"])
        audit.record(
            actor=owner,
            action="upi_payment.approve",
            entity_type="upi_payment_request",
            entity_id=request.pk,
            library=library,
            changes={
                "receipt": payment.receipt_number,
                "seat": seat_label,
                "alternative_seat": bool(seat_id and request.seat_id and seat_id != request.seat_id),
            },
        )
        notifications.notify(
            recipient=request.student,
            type="upi_payment_approved",
            title="Payment approved",
            body=f"{library.name} confirmed your payment. {summary}",
            dedup_key=f"upi:{request.pk}:approved:{request.student_id}",
            entity=("membership", membership.pk),
        )
    logger.info(
        "UPI payment request approved",
        extra={"request_id": str(request.pk), "payment_id": str(payment.pk), "owner_id": str(owner.pk)},
    )
    return request
