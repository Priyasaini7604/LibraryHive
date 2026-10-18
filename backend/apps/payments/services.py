"""Payments: orders, verification, webhooks, confirmation, reconciliation (SPEC.md 4.3, BACKEND_ARCHITECTURE.md 10).

Principles (SECURITY.md section 10): the browser is never trusted, the amount comes from the plan row, and
confirmation is one function that locks the Payment row and is a no-op when the payment is already a success,
so the checkout callback, the webhook and the reconcile job can arrive in any order and any number of times.

Locking order (BACKEND_ARCHITECTURE.md 8.1): Seat, then Payment, then Hold. `confirm_payment` takes the Payment
first and the Seat second, as the table there lists it; `create_order` takes the Seat first. They never wait on
each other in a cycle because `create_order` does not hold a Payment lock while it waits for a Seat.

Not in T14: renewal orders and offline payments (T15), refunds (PAY-14, manual).
"""

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.dates import business_today
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.memberships import selectors as membership_selectors
from apps.memberships import services as membership_services
from apps.memberships.models import Membership
from apps.notifications import services as notifications
from apps.seats.models import Seat, SeatHold

from . import gateway
from .models import Payment, PaymentWebhookEvent, next_receipt_number

logger = logging.getLogger("apps.payments")
security_logger = logging.getLogger("apps.security")

ERROR_TEXT_MAX = 2000


def to_paise(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# --- Orders (#41, new booking) -------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderResult:
    payment: Payment
    key_id: str
    order_id: str
    amount_paise: int
    currency: str


def _live_booking_hold(hold: SeatHold, *, now) -> bool:
    return hold.status == SeatHold.Status.PENDING and hold.expires_at is not None and hold.expires_at > now


def lock_pending_for_hold(hold_id) -> list[Payment]:
    """Lock a hold's pending payments. Anyone who also takes the Seat lock must call this *first*: confirmation
    locks Payment -> Seat -> Hold, so any other order would deadlock against it."""
    return list(
        Payment.objects.select_for_update().filter(hold_id=hold_id, status=Payment.Status.PENDING).order_by("pk")
    )


def cancel_locked(payments: list[Payment]) -> None:
    """Close payments returned by `lock_pending_for_hold` as `cancelled` (money that still arrives wins later)."""
    for payment in payments:
        payment.move_to(Payment.Status.CANCELLED)
        payment.save(update_fields=["status", "updated_at"])


def create_order(*, student, hold_id) -> OrderResult:
    """Create the gateway order for the student's own live booking hold (#41).

    The amount is the plan's price from the database. One pending order per hold: an older pending one
    becomes `cancelled`. The gateway is called before the row is written because an online payment must carry
    its order id (`payment_online_has_order`); a gateway failure therefore leaves no row and answers 502.
    """
    now = timezone.now()
    hold = (
        SeatHold.objects.select_related("seat", "library", "plan")
        .filter(pk=hold_id, student=student, kind=SeatHold.Kind.BOOKING)
        .first()
    )
    if hold is None:
        raise NotFound()
    if not _live_booking_hold(hold, now=now):
        raise Conflict("Your seat hold expired.", code="HOLD_EXPIRED")
    plan = hold.plan
    if not plan.is_active:
        raise Conflict("This plan is no longer available. Please choose another.", code="PLAN_INACTIVE")

    amount = plan.price
    amount_paise = to_paise(amount)
    receipt = next_receipt_number(business_today().year)
    client = gateway.get_gateway()
    order = client.create_order(
        amount_paise=amount_paise, receipt=receipt, notes={"hold_id": str(hold.pk), "student_id": str(student.pk)}
    )

    with transaction.atomic():
        older = lock_pending_for_hold(hold.pk)
        Seat.objects.select_for_update().get(pk=hold.seat_id)
        locked_hold = SeatHold.objects.select_for_update().get(pk=hold.pk)
        if not _live_booking_hold(locked_hold, now=timezone.now()):
            raise Conflict("Your seat hold expired.", code="HOLD_EXPIRED")
        cancel_locked(older)
        payment = Payment.objects.create(
            library=hold.library,
            student=student,
            hold=locked_hold,
            plan=plan,
            purpose=Payment.Purpose.NEW_MEMBERSHIP,
            channel=Payment.Channel.ONLINE,
            method=Payment.Method.GATEWAY,
            amount=amount,
            currency="INR",
            gateway_order_id=order.order_id,
            receipt_number=receipt,
        )
    logger.info(
        "Payment order created",
        extra={"order_id": order.order_id, "payment_id": str(payment.pk), "student_id": str(student.pk)},
    )
    return OrderResult(
        payment=payment,
        key_id=client.key_id,
        order_id=order.order_id,
        amount_paise=amount_paise,
        currency=order.currency,
    )


def create_renewal_order(*, student, membership_id, plan_id=None) -> OrderResult:
    """Create the gateway order for renewing the student's own membership (#41, renewal part, MEM-05).

    Opens when `next_due_date` is within 7 days or already past. The optional `plan_id` changes the plan for
    the new period and must be active and belong to the same library. The amount is the plan price.
    """
    today = business_today()
    membership = (
        Membership.objects.select_related("library", "plan", "seat").filter(pk=membership_id, student=student).first()
    )
    if membership is None:
        raise NotFound()
    plan = membership_services.plan_for_renewal(membership, plan_id)
    membership_services.require_renewable(membership, today=today)

    amount = plan.price
    amount_paise = to_paise(amount)
    receipt = next_receipt_number(today.year)
    client = gateway.get_gateway()
    order = client.create_order(
        amount_paise=amount_paise,
        receipt=receipt,
        notes={"membership_id": str(membership.pk), "student_id": str(student.pk)},
    )

    with transaction.atomic():
        locked = Membership.objects.select_for_update().get(pk=membership.pk)
        membership_services.require_renewable(locked, today=today)
        payment = Payment.objects.create(
            library=membership.library,
            student=student,
            membership=locked,
            plan=plan,
            purpose=Payment.Purpose.RENEWAL,
            channel=Payment.Channel.ONLINE,
            method=Payment.Method.GATEWAY,
            amount=amount,
            currency="INR",
            gateway_order_id=order.order_id,
            receipt_number=receipt,
        )
    logger.info(
        "Renewal order created",
        extra={"order_id": order.order_id, "payment_id": str(payment.pk), "student_id": str(student.pk)},
    )
    return OrderResult(
        payment=payment,
        key_id=client.key_id,
        order_id=order.order_id,
        amount_paise=amount_paise,
        currency=order.currency,
    )


# --- Confirmation (one function, idempotent) ---------------------------------------------------------------


def _seat_is_lost(payment: Payment, seat: Seat, hold: SeatHold, *, now) -> bool:
    """True if the booked seat can no longer be given to this student (SPEC.md 4.3)."""
    if not seat.is_active or seat.is_disabled or hold.status == SeatHold.Status.COMPLETED:
        return True
    if membership_selectors.active_membership_exists(seat):
        return True
    if SeatHold.objects.live(now).filter(seat=seat).exclude(pk=hold.pk).exists():
        return True
    return membership_selectors.student_is_member(payment.student, payment.library)


def _mark_needs_refund(payment: Payment, *, gateway_payment_id: str, via: str, now) -> None:
    payment.move_to(Payment.Status.NEEDS_REFUND)
    payment.gateway_payment_id = gateway_payment_id
    payment.verified_via = via
    payment.paid_at = now
    payment.failure_reason = "The seat was no longer available when the payment arrived."
    payment.save()
    audit.record(
        actor=None,
        action="payment.status_change",
        entity_type="payment",
        entity_id=payment.pk,
        library=payment.library,
        changes={"status": ["pending", "needs_refund"], "via": via},
    )
    logger.warning(
        "Payment received but seat lost",
        extra={
            "payment_id": str(payment.pk),
            "order_id": payment.gateway_order_id,
            "student_id": str(payment.student_id),
        },
    )
    entity = ("payment", payment.pk)
    for recipient, body in (
        (payment.student, "We received your payment but the seat was taken. The library will refund you."),
        (payment.library.owner, "A payment arrived after its seat was no longer available and needs a refund."),
    ):
        notifications.notify(
            recipient=recipient,
            type="payment_needs_refund",
            title="Payment needs a refund",
            body=body,
            dedup_key=f"payment:{payment.pk}:payment_needs_refund:{recipient.pk}",
            entity=entity,
        )


def _confirm_new_membership(payment: Payment, *, gateway_payment_id: str, via: str) -> Payment:
    now = timezone.now()
    hold = SeatHold.objects.select_related("seat", "library", "plan", "student").get(pk=payment.hold_id)
    seat = Seat.objects.select_for_update().get(pk=hold.seat_id)
    hold = (
        SeatHold.objects.select_for_update(of=("self",))
        .select_related("seat", "library", "plan", "student")
        .get(pk=hold.pk)
    )

    if _seat_is_lost(payment, seat, hold, now=now):
        _mark_needs_refund(payment, gateway_payment_id=gateway_payment_id, via=via, now=now)
        return payment

    # The hold is completed, or re-acquired if it expired (or was released) but the seat is still free.
    try:
        with transaction.atomic():
            hold.status = SeatHold.Status.COMPLETED
            hold.closed_at = now
            hold.save(update_fields=["status", "closed_at", "updated_at"])
            start = business_today()
            membership = membership_services.activate_from_hold(hold=hold, start_date=start)
    except IntegrityError:
        # Another writer won the seat between the checks and the insert: the unique constraints decide.
        _mark_needs_refund(payment, gateway_payment_id=gateway_payment_id, via=via, now=now)
        return payment

    payment.move_to(Payment.Status.SUCCESS)
    payment.gateway_payment_id = gateway_payment_id
    payment.verified_via = via
    payment.paid_at = now
    payment.membership = membership
    payment.period_start = membership.start_date
    payment.period_end = membership.next_due_date
    payment.failure_reason = ""
    payment.save()
    audit.record(
        actor=None,
        action="payment.status_change",
        entity_type="payment",
        entity_id=payment.pk,
        library=payment.library,
        changes={"status": ["pending", "success"], "via": via, "receipt": payment.receipt_number},
    )
    logger.info(
        "Payment verified successfully",
        extra={
            "order_id": payment.gateway_order_id,
            "payment_id": str(payment.pk),
            "student_id": str(payment.student_id),
        },
    )
    notifications.notify(
        recipient=payment.student,
        type="booking_confirmed",
        title="Your seat is booked",
        body=f"Seat {seat.label} at {payment.library.name} is yours until {membership.next_due_date:%d %b %Y}.",
        dedup_key=f"payment:{payment.pk}:booking_confirmed:{payment.student_id}",
        entity=("membership", membership.pk),
    )
    notifications.notify(
        recipient=payment.library.owner,
        type="payment_received",
        title="Payment received",
        body=f"{payment.student.name} paid {payment.amount} for seat {seat.label}.",
        dedup_key=f"payment:{payment.pk}:payment_received:{payment.library.owner_id}",
        entity=("payment", payment.pk),
    )
    return payment


def _confirm_renewal(payment: Payment, *, gateway_payment_id: str, via: str) -> Payment:
    """Extend the membership once the renewal money is verified (SPEC.md 4.3). The seat is kept.

    Locks Payment (held by the caller) then Membership. If the membership was archived while the student was
    paying, the money cannot buy a period, so the payment becomes `needs_refund`.
    """
    now = timezone.now()
    membership = (
        Membership.objects.select_for_update(of=("self",))
        .select_related("seat", "library", "plan", "student")
        .get(pk=payment.membership_id)
    )
    if membership.state != Membership.State.ACTIVE:
        _mark_needs_refund(payment, gateway_payment_id=gateway_payment_id, via=via, now=now)
        return payment

    period_start, period_end = membership_services.apply_renewal(
        membership=membership, plan=payment.plan, today=business_today(), actor=payment.student
    )
    payment.move_to(Payment.Status.SUCCESS)
    payment.gateway_payment_id = gateway_payment_id
    payment.verified_via = via
    payment.paid_at = now
    payment.period_start = period_start
    payment.period_end = period_end
    payment.failure_reason = ""
    payment.save()
    audit.record(
        actor=None,
        action="payment.status_change",
        entity_type="payment",
        entity_id=payment.pk,
        library=payment.library,
        changes={"status": ["pending", "success"], "via": via, "receipt": payment.receipt_number},
    )
    logger.info(
        "Renewal payment verified successfully",
        extra={
            "order_id": payment.gateway_order_id,
            "payment_id": str(payment.pk),
            "student_id": str(payment.student_id),
        },
    )
    _notify_payment_received(
        payment, membership, student_body=f"Your membership is renewed until {period_end:%d %b %Y}."
    )
    return payment


def _notify_payment_received(payment: Payment, membership: Membership, *, student_body: str) -> None:
    """`payment_received` to the student and the owner for a renewal (dedup key SPEC.md 4.5)."""
    for recipient, body in (
        (payment.student, student_body),
        (
            payment.library.owner,
            f"{payment.student.name} paid {payment.amount} for a renewal of seat {membership.seat.label}.",
        ),
    ):
        notifications.notify(
            recipient=recipient,
            type="payment_received",
            title="Payment received",
            body=body,
            dedup_key=f"payment:{payment.pk}:payment_received:{recipient.pk}",
            entity=("payment", payment.pk),
        )


OFFLINE_METHODS = (Payment.Method.CASH, Payment.Method.UPI_DIRECT, Payment.Method.BANK_TRANSFER)
OFFLINE_BACKDATE_DAYS = 30


def record_offline_payment(
    *,
    membership: Membership,
    plan,
    purpose: str,
    method: str,
    recorded_by,
    period_start,
    period_end,
    paid_at=None,
    notes: str = "",
) -> Payment:
    """Write the successful offline payment an owner took in person (PAY-07, SPEC.md 4.3).

    Called inside the admission or renewal transaction, which already holds the membership lock. The amount is
    the plan price, never a client value. `paid_at` defaults to now and may not be in the future or more than
    30 days back. Gets a receipt number from the sequence, `recorded_by` is the owner, and the student is told.
    """
    now = timezone.now()
    if method not in OFFLINE_METHODS:
        raise ValidationFailed(details={"method": ["Choose cash, UPI or bank transfer."]})
    paid_at = paid_at or now
    if paid_at > now or paid_at < now - timedelta(days=OFFLINE_BACKDATE_DAYS):
        raise ValidationFailed(
            details={"paid_at": ["The payment date must be within the last 30 days, not in the future."]}
        )
    payment = Payment.objects.create(
        library=membership.library,
        student=membership.student,
        membership=membership,
        plan=plan,
        purpose=purpose,
        channel=Payment.Channel.OFFLINE,
        method=method,
        status=Payment.Status.SUCCESS,
        amount=plan.price,
        currency="INR",
        period_start=period_start,
        period_end=period_end,
        verified_via=Payment.VerifiedVia.MANUAL,
        receipt_number=next_receipt_number(business_today().year),
        recorded_by=recorded_by,
        notes=notes.strip(),
        paid_at=paid_at,
    )
    audit.record(
        actor=recorded_by,
        action="payment.record_offline",
        entity_type="payment",
        entity_id=payment.pk,
        library=membership.library,
        changes={"receipt": payment.receipt_number, "method": method, "amount": str(payment.amount)},
    )
    logger.info(
        "Offline payment recorded",
        extra={"payment_id": str(payment.pk), "membership_id": str(membership.pk), "owner_id": str(recorded_by.pk)},
    )
    notifications.notify(
        recipient=membership.student,
        type="payment_received",
        title="Payment recorded",
        body=f"{membership.library.name} recorded your payment of {payment.amount}.",
        dedup_key=f"payment:{payment.pk}:payment_received:{membership.student_id}",
        entity=("payment", payment.pk),
    )
    return payment


@transaction.atomic
def confirm_payment(*, order_id: str, gateway_payment_id: str, via: str) -> Payment | None:
    """Confirm an online payment once money has been verified by checkout, webhook or reconcile.

    Locks the Payment row; a payment that is already `success` (or `needs_refund`) is returned as it is, so any
    repeat is harmless. A `failed` or `cancelled` payment still confirms when captured money arrives: money
    received always wins over a client-side cancel (BACKEND_ARCHITECTURE.md 10). Returns None for an unknown order.
    """
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("library__owner", "student", "plan")
        .filter(gateway_order_id=order_id)
        .first()
    )
    if payment is None:
        return None
    if payment.status in (Payment.Status.SUCCESS, Payment.Status.NEEDS_REFUND):
        return payment
    other = Payment.objects.filter(gateway_payment_id=gateway_payment_id).exclude(pk=payment.pk).exists()
    if other:
        raise ValueError("This gateway payment id already belongs to another payment.")
    if payment.purpose == Payment.Purpose.RENEWAL:
        return _confirm_renewal(payment, gateway_payment_id=gateway_payment_id, via=via)
    return _confirm_new_membership(payment, gateway_payment_id=gateway_payment_id, via=via)


# --- Checkout verification (#42) --------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyResult:
    payment: Payment
    membership: Membership | None


def verify_checkout(*, student, order_id: str, payment_id: str, signature: str) -> VerifyResult:
    """Verify the checkout callback server-side and confirm (#42).

    The payment is looked up among the caller's own payments only (404 otherwise). The callback is just a
    hint: nothing changes unless the HMAC-SHA256 signature matches. A forged one is a 400 and a security log.
    """
    payment = Payment.objects.filter(gateway_order_id=order_id, student=student).first()
    if payment is None:
        raise NotFound()
    if not gateway.get_gateway().verify_checkout_signature(
        order_id=order_id, payment_id=payment_id, signature=signature
    ):
        security_logger.warning(
            "security.invalid_payment_signature", extra={"order_id": order_id, "student_id": str(student.pk)}
        )
        raise ValidationFailed("We couldn't verify this payment.", code="INVALID_SIGNATURE")

    confirmed = confirm_payment(order_id=order_id, gateway_payment_id=payment_id, via=Payment.VerifiedVia.CHECKOUT)
    if confirmed is None:  # cannot happen: the payment was found above and rows are never deleted
        raise NotFound()
    if confirmed.status == Payment.Status.NEEDS_REFUND:
        raise Conflict(
            "Your payment was received but the seat was no longer available. The library will refund you.",
            code="SEAT_LOST_REFUND_PENDING",
        )
    return VerifyResult(payment=confirmed, membership=confirmed.membership)


# --- Webhook (#43) ------------------------------------------------------------------------------------------


def _entity(payload: dict, kind: str) -> dict:
    return ((payload.get("payload") or {}).get(kind) or {}).get("entity") or {}


def _process_event(event_type: str, payload: dict) -> str:
    """Apply one verified event. Returns the `PaymentWebhookEvent.result` value."""
    payment_entity = _entity(payload, "payment")
    if event_type in ("payment.captured", "order.paid"):
        order_id = payment_entity.get("order_id") or _entity(payload, "order").get("id")
        payment_id = payment_entity.get("id")
        if not order_id or not payment_id:
            return PaymentWebhookEvent.Result.IGNORED_UNKNOWN
        known = Payment.objects.filter(gateway_order_id=order_id).first()
        if known is None:
            return PaymentWebhookEvent.Result.IGNORED_UNKNOWN
        paid = payment_entity.get("amount")
        if paid is not None and int(paid) != to_paise(known.amount):
            raise ValueError(f"Captured amount {paid} does not match the order amount for payment {known.pk}.")
        confirm_payment(order_id=order_id, gateway_payment_id=payment_id, via=Payment.VerifiedVia.WEBHOOK)
        return PaymentWebhookEvent.Result.PROCESSED
    if event_type == "payment.failed":
        order_id = payment_entity.get("order_id")
        if not order_id:
            return PaymentWebhookEvent.Result.IGNORED_UNKNOWN
        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(gateway_order_id=order_id).first()
            if payment is None:
                return PaymentWebhookEvent.Result.IGNORED_UNKNOWN
            if payment.status == Payment.Status.PENDING:  # a success or refund state is never overwritten
                payment.move_to(Payment.Status.FAILED)
                payment.failure_reason = str(payment_entity.get("error_description") or "Payment failed.")[:255]
                payment.save()
                audit.record(
                    actor=None,
                    action="payment.status_change",
                    entity_type="payment",
                    entity_id=payment.pk,
                    library=payment.library,
                    changes={"status": ["pending", "failed"], "via": "webhook"},
                )
        return PaymentWebhookEvent.Result.PROCESSED
    return PaymentWebhookEvent.Result.IGNORED_UNKNOWN


def handle_webhook(*, raw_body: bytes, signature: str, event_id: str) -> str:
    """Handle a gateway webhook (#43). Returns the stored result; raises only for an invalid request.

    The signature is checked on the raw bytes first. An invalid one is rejected (400) and only logged, never
    stored. After a valid signature the answer is always 200, even when processing fails, so the gateway does
    not retry forever; the outcome is kept on the event row and in the log.
    """
    if not gateway.get_gateway().verify_webhook_signature(raw_body=raw_body, signature=signature):
        security_logger.warning("security.invalid_webhook_signature", extra={"event_id": event_id or ""})
        raise ValidationFailed("Invalid signature.", code="INVALID_SIGNATURE")
    if not event_id or len(event_id) > 64:
        raise ValidationFailed("Missing or invalid event id.")
    try:
        payload = json.loads(raw_body)
        event_type = str(payload["event"])[:60]
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationFailed("The event body is not valid.") from exc

    try:
        with transaction.atomic():
            event = PaymentWebhookEvent.objects.create(event_id=event_id, event_type=event_type, payload=payload)
    except IntegrityError:
        logger.info("Duplicate webhook ignored", extra={"event_id": event_id})
        return PaymentWebhookEvent.Result.IGNORED_DUPLICATE

    try:
        result = _process_event(event_type, payload)
        error = ""
    except Exception as exc:
        result, error = PaymentWebhookEvent.Result.ERROR, f"{type(exc).__name__}: {exc}"[:ERROR_TEXT_MAX]
        logger.exception("Webhook processing failed", extra={"event_id": event_id, "event_type": event_type})
    event.result = result
    event.error = error
    event.processed_at = timezone.now()
    event.save(update_fields=["result", "error", "processed_at", "updated_at"])
    return result


# --- Reconciliation (job step, T24 wires it) ------------------------------------------------------------------


def reconcile_stale_orders(*, now=None) -> dict[str, int]:
    """Settle online payments still pending 30 minutes after creation (BACKEND_ARCHITECTURE.md 10).

    Captured at the gateway: confirm (`verified_via=reconcile`). Nothing captured and the hold is dead: cancel.
    One failing row (for example a gateway outage) is logged and does not stop the others.
    """
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=settings.PAYMENT_RECONCILE_AFTER_MINUTES)
    stale = list(
        Payment.objects.filter(
            channel=Payment.Channel.ONLINE, status=Payment.Status.PENDING, created_at__lte=cutoff
        ).select_related("hold")
    )
    counts = {"checked": len(stale), "confirmed": 0, "cancelled": 0, "errors": 0}
    client = gateway.get_gateway()
    for payment in stale:
        try:
            captured = [
                p for p in client.fetch_order_payments(order_id=payment.gateway_order_id) if p.status == "captured"
            ]
            if captured:
                confirm_payment(
                    order_id=payment.gateway_order_id,
                    gateway_payment_id=captured[0].payment_id,
                    via=Payment.VerifiedVia.RECONCILE,
                )
                counts["confirmed"] += 1
            elif payment.hold is None or not _live_booking_hold(payment.hold, now=now):
                with transaction.atomic():
                    locked = Payment.objects.select_for_update().get(pk=payment.pk)
                    if locked.status == Payment.Status.PENDING:
                        locked.move_to(Payment.Status.CANCELLED)
                        locked.save()
                        counts["cancelled"] += 1
        except Exception:
            counts["errors"] += 1
            logger.exception("Payment reconciliation failed", extra={"payment_id": str(payment.pk)})
    logger.info("Payments reconciled", extra=counts)
    return counts
