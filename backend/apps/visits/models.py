from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel


class VisitRequest(BaseModel):
    """A student's request to look around a library before joining (SPEC.md 3.17, 4.11).

    There is no calendar or slot-capacity engine in the MVP: the owner just accepts or rejects.
    """

    class Slot(models.TextChoices):
        MORNING = "morning", "Morning"
        AFTERNOON = "afternoon", "Afternoon"
        EVENING = "evening", "Evening"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="visit_requests")
    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="visit_requests")
    preferred_date = models.DateField()
    preferred_slot = models.CharField(max_length=10, choices=Slot.choices)
    student_note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    owner_note = models.CharField(max_length=500, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["library", "status", "preferred_date"], name="visit_library_status_idx"),
            models.Index(fields=["student", "-created_at"], name="visit_student_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "library"],
                condition=Q(status="pending"),
                name="visit_one_pending_per_student_library",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "cancelled"]) | Q(decided_at__isnull=False),
                name="visit_decided_has_time",
            ),
        ]

    def __str__(self):
        return f"visit {self.preferred_date} ({self.status})"
