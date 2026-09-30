from django.conf import settings
from django.db import models
from apps.core.models import BaseModel
from apps.libraries.models import Library


class Complaint(BaseModel):
    CATEGORY_CHOICES = (
        ("cleanliness", "Cleanliness"),
        ("seat_issue", "Seat Issue"),
        ("staff_behaviour", "Staff Behaviour"),
        ("other", "Other"),
    )
    STATUS_CHOICES = (
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="complaints",
    )
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="complaints")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    resolution_note = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.library.name} - {self.category} ({self.status})"
