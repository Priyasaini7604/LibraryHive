from django.conf import settings
from django.db import models
from apps.core.models import BaseModel


class Library(BaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="libraries",
    )
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    opens_at = models.TimeField()
    closes_at = models.TimeField()
    domains_catered = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated, e.g. UPSC,SSC,NEET",
    )

    def __str__(self):
        return self.name


class Seat(BaseModel):
    STATUS_CHOICES = (
        ("empty", "Empty"),
        ("reserved", "Reserved"),
        ("occupied", "Occupied"),
    )

    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="seats")
    label = models.CharField(max_length=20)  # e.g. "A-3"
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="empty")

    class Meta:
        unique_together = ("library", "label")

    def __str__(self):
        return f"{self.library.name} - {self.label} ({self.status})"


class PricingPlan(BaseModel):
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(max_length=50)  # e.g. "Monthly"
    duration_days = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.library.name} - {self.name} (₹{self.price})"
