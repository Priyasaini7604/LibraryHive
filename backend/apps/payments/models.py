from django.conf import settings
from django.db import connection, models
from django.db.models import Q

from apps.core.models import BaseModel


def next_receipt_number(year: int) -> str:
    """`LH-{YYYY}-{seq:06d}` from the PostgreSQL sequence `payment_receipt_seq` (SPEC.md 3.11).

    The sequence is global, so numbers are unique and only ever increase. Gaps are fine: a number is drawn
    when an order is created, whether or not it is ever paid.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('payment_receipt_seq')")
        sequence = cursor.fetchone()[0]
    return f"LH-{year}-{sequence:06d}"


class Payment(BaseModel):
    """The immutable money ledger (SPEC.md 3.11, 4.3). Rows are never deleted.

    Amount, plan, library, student and period never change once set. Status moves only along the
    transitions in `ALLOWED_TRANSITIONS`; use `Payment.move_to()` instead of assigning `status`.
    """

    class Purpose(models.TextChoices):
        NEW_MEMBERSHIP = "new_membership", "New membership"
        RENEWAL = "renewal", "Renewal"

    class Channel(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    class Method(models.TextChoices):
        GATEWAY = "gateway", "Gateway"
        CASH = "cash", "Cash"
        UPI_DIRECT = "upi_direct", "UPI (direct)"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        NEEDS_REFUND = "needs_refund", "Needs refund"

    class VerifiedVia(models.TextChoices):
        CHECKOUT = "checkout", "Checkout"
        WEBHOOK = "webhook", "Webhook"
        RECONCILE = "reconcile", "Reconcile"
        MANUAL = "manual", "Manual"

    # failed and cancelled can still become success or needs_refund: money that arrives always wins (BACKEND 10).
    ALLOWED_TRANSITIONS = {
        "pending": {"success", "failed", "cancelled", "needs_refund"},
        "failed": {"success", "needs_refund"},
        "cancelled": {"success", "needs_refund"},
        "success": set(),
        "needs_refund": set(),
    }
    IMMUTABLE_FIELDS = ("library_id", "student_id", "plan_id", "purpose", "channel", "amount", "currency")

    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="payments")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    membership = models.ForeignKey(
        "memberships.Membership", on_delete=models.PROTECT, null=True, blank=True, related_name="payments"
    )
    hold = models.ForeignKey("seats.SeatHold", on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    plan = models.ForeignKey("libraries.PricingPlan", on_delete=models.PROTECT, related_name="payments")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    method = models.CharField(max_length=15, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    gateway_order_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    gateway_payment_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    verified_via = models.CharField(max_length=10, choices=VerifiedVia.choices, null=True, blank=True)  # noqa: DJ001
    receipt_number = models.CharField(max_length=32, unique=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["library", "-paid_at"], name="payment_library_paid_idx"),
            models.Index(fields=["student", "-created_at"], name="payment_student_created_idx"),
            models.Index(fields=["status", "created_at"], name="payment_status_created_idx"),
            models.Index(fields=["membership"], name="payment_membership_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(period_start__isnull=True)
                | Q(period_end__isnull=True)
                | Q(period_end__gt=models.F("period_start")),
                name="payment_period_order",
            ),
            models.CheckConstraint(
                condition=~Q(channel="online") | Q(gateway_order_id__isnull=False), name="payment_online_has_order"
            ),
            models.CheckConstraint(
                condition=~Q(channel="offline") | (Q(recorded_by__isnull=False) & Q(status="success")),
                name="payment_offline_recorded",
            ),
            models.CheckConstraint(
                condition=~Q(status="success")
                | (
                    Q(paid_at__isnull=False)
                    & Q(period_start__isnull=False)
                    & Q(period_end__isnull=False)
                    & Q(membership__isnull=False)
                ),
                name="payment_success_complete",
            ),
            models.CheckConstraint(
                condition=~Q(purpose="renewal") | Q(membership__isnull=False), name="payment_renewal_has_membership"
            ),
            models.CheckConstraint(
                condition=Q(purpose__in=["new_membership", "renewal"])
                & Q(channel__in=["online", "offline"])
                & Q(method__in=["gateway", "cash", "upi_direct", "bank_transfer"])
                & Q(status__in=["pending", "success", "failed", "cancelled", "needs_refund"]),
                name="payment_choices_valid",
            ),
        ]

    def __str__(self):
        return f"{self.receipt_number} {self.status}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._loaded = {name: getattr(instance, name) for name in cls.IMMUTABLE_FIELDS}
        return instance

    def save(self, *args, **kwargs):
        loaded = getattr(self, "_loaded", None)
        if not self._state.adding and loaded is not None:
            changed = [name for name in self.IMMUTABLE_FIELDS if getattr(self, name) != loaded[name]]
            if changed:
                raise TypeError(f"Payment fields are immutable once created: {', '.join(changed)}.")
        super().save(*args, **kwargs)
        self._loaded = {name: getattr(self, name) for name in self.IMMUTABLE_FIELDS}

    def delete(self, *args, **kwargs):
        raise TypeError("Payments are append-only and cannot be deleted.")

    def move_to(self, new_status: str) -> None:
        """Change `status` along an allowed transition only (SPEC.md 4.3); the caller saves."""
        if new_status == self.status:
            return
        if new_status not in self.ALLOWED_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"A {self.status} payment cannot become {new_status}.")
        self.status = new_status


class PaymentWebhookEvent(BaseModel):
    """A signature-valid gateway event (SPEC.md 3.12). Forged requests are rejected and never stored."""

    class Result(models.TextChoices):
        PROCESSED = "processed", "Processed"
        IGNORED_DUPLICATE = "ignored_duplicate", "Ignored duplicate"
        IGNORED_UNKNOWN = "ignored_unknown", "Ignored unknown"
        ERROR = "error", "Error"

    event_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=60)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=20, choices=Result.choices, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} {self.event_id}"
