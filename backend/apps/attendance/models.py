from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel


class AttendanceRecord(BaseModel):
    """One check-in and, later, one check-out of a member (SPEC.md 3.15, 4.9).

    A student has at most one open record anywhere (`attendance_one_open_per_student`, the database backstop
    for double taps). `seat` is a snapshot of the member's seat at check-in. Check-in is trust-based: there is
    no geofence or QR in the MVP.
    """

    class Method(models.TextChoices):
        SELF = "self", "Self"
        OWNER = "owner", "Owner"
        AUTO = "auto", "Automatic"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        AUTO_CLOSED = "auto_closed", "Auto-closed"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_records")
    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="attendance_records")
    membership = models.ForeignKey(
        "memberships.Membership", on_delete=models.PROTECT, related_name="attendance_records"
    )
    seat = models.ForeignKey("seats.Seat", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    date = models.DateField()
    check_in_at = models.DateTimeField()
    check_out_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    check_in_method = models.CharField(max_length=10, choices=Method.choices)
    check_out_method = models.CharField(max_length=10, choices=Method.choices, null=True, blank=True)  # noqa: DJ001
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-check_in_at"]
        indexes = [
            models.Index(fields=["library", "date"], name="attendance_library_date_idx"),
            models.Index(fields=["student", "-date"], name="attendance_student_date_idx"),
            models.Index(fields=["library", "status"], name="attendance_library_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student"], condition=Q(check_out_at__isnull=True), name="attendance_one_open_per_student"
            ),
            models.CheckConstraint(
                condition=Q(check_out_at__isnull=True) | Q(check_out_at__gt=F("check_in_at")),
                name="attendance_checkout_after_checkin",
            ),
            models.CheckConstraint(
                condition=(Q(status="open") & Q(check_out_at__isnull=True))
                | (~Q(status="open") & Q(check_out_at__isnull=False)),
                name="attendance_status_matches_checkout",
            ),
        ]

    def __str__(self):
        return f"{self.student_id} {self.date} {self.status}"
