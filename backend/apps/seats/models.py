from django.db import models
from apps.core.models import BaseModel
from apps.libraries.models import Library


class Seat(BaseModel):
    STATUS_CHOICES = (
        ("empty", "Empty"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
    )

    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name="seats",
    )
    label = models.CharField(max_length=50)  # e.g. "Row A - Seat 1"
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="empty",
    )

    class Meta:
        unique_together = ("library", "label")
        ordering = ["label"]

    def __str__(self):
        return f"{self.library.name} - {self.label} ({self.status})"
