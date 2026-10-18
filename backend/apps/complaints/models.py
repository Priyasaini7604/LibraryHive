from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel


class Complaint(BaseModel):
    """A member's grievance about a library and the owner's answer (SPEC.md 3.16, 4.10).

    Only the library's owner changes the status. Reopening is not in the MVP: the student files a new complaint.
    The optional photo (CMP-06, P1) needs private object storage and is not part of this model yet.
    """

    class Category(models.TextChoices):
        NOISE = "noise", "Noise"
        AC = "ac", "Air conditioning"
        WIFI = "wifi", "Wi-Fi"
        CLEANLINESS = "cleanliness", "Cleanliness"
        POWER_LIGHTING = "power_lighting", "Power and lighting"
        SEAT_FURNITURE = "seat_furniture", "Seat and furniture"
        STAFF = "staff", "Staff"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    # Allowed owner transitions (SPEC.md 4.10). `resolved` is final.
    TRANSITIONS = {"open": {"in_progress", "resolved"}, "in_progress": {"resolved"}, "resolved": set()}

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaints")
    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="complaints")
    membership = models.ForeignKey("memberships.Membership", on_delete=models.PROTECT, related_name="complaints")
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    owner_response = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["library", "status", "-created_at"], name="complaint_library_status_idx"),
            models.Index(fields=["student", "-created_at"], name="complaint_student_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(Q(status="resolved") & Q(resolved_at__isnull=False))
                | (~Q(status="resolved") & Q(resolved_at__isnull=True)),
                name="complaint_resolved_has_time",
            ),
        ]

    def __str__(self):
        return f"{self.category} ({self.status})"
