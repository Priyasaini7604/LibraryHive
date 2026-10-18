from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

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
