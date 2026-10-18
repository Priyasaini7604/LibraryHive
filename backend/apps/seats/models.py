from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import BaseModel


class Seat(BaseModel):
    """One physical seat of a library (SPEC.md 3.8, decision D1: sold full-day).

    Its status (empty, reserved, occupied, disabled) is derived, never stored
    (SPEC.md 4.1). `is_active=False` means removed: the row is kept as history.
    """

    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="seats")
    label = models.CharField(max_length=50)
    row_label = models.CharField(max_length=10, blank=True)
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_disabled = models.BooleanField(default=False)
    disabled_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["row_label", "position", "label"]
        indexes = [
            models.Index(fields=["library", "is_active", "row_label", "position"], name="seat_library_layout_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                "library",
                Lower("label"),
                condition=Q(is_active=True),
                name="seat_unique_active_label",
            ),
            models.CheckConstraint(condition=Q(is_disabled=False) | Q(is_active=True), name="seat_disabled_is_active"),
        ]

    def __str__(self):
        return f"{self.label} ({self.library_id})"


class SeatHoldQuerySet(models.QuerySet):
    def live(self, now=None):
        """Holds that currently block the seat (SPEC.md 3.9 liveness rule).

        A pending hold whose `expires_at` has passed is dead for every read, even before the cleanup step
        marks it `expired`. Manual holds have no expiry and stay live until released.
        """
        now = now or timezone.now()
        return self.filter(status=SeatHold.Status.PENDING).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


class SeatHold(BaseModel):
    """A student's 15-minute booking hold or an owner's manual hold on one seat (SPEC.md 3.9)."""

    class Kind(models.TextChoices):
        BOOKING = "booking", "Booking"
        OWNER_MANUAL = "owner_manual", "Owner manual"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"
        RELEASED = "released", "Released"

    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, related_name="holds")
    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="seat_holds")
    kind = models.CharField(max_length=15, choices=Kind.choices)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="seat_holds"
    )
    plan = models.ForeignKey(
        "libraries.PricingPlan", on_delete=models.PROTECT, null=True, blank=True, related_name="seat_holds"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = SeatHoldQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["library", "status"], name="seathold_library_status_idx"),
            models.Index(fields=["status", "expires_at"], name="seathold_status_expiry_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["seat"], condition=Q(status="pending"), name="seathold_one_pending_per_seat"
            ),
            models.UniqueConstraint(
                fields=["student", "library"],
                condition=Q(status="pending", kind="booking"),
                name="seathold_one_pending_per_student_library",
            ),
            models.CheckConstraint(
                condition=~Q(kind="booking")
                | (Q(student__isnull=False) & Q(plan__isnull=False) & Q(expires_at__isnull=False)),
                name="seathold_booking_fields",
            ),
            models.CheckConstraint(
                condition=~Q(kind="owner_manual") | (Q(expires_at__isnull=True) & ~Q(reason="")),
                name="seathold_manual_fields",
            ),
            models.CheckConstraint(condition=Q(kind__in=["booking", "owner_manual"]), name="seathold_kind_valid"),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "completed", "expired", "cancelled", "released"]),
                name="seathold_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.kind} hold on {self.seat_id} ({self.status})"
