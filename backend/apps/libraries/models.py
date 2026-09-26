from django.conf import settings
from django.db import models
from apps.core.models import BaseModel


class Library(BaseModel):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library",
    )
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    total_seats = models.PositiveIntegerField(default=0)
    opens_at = models.TimeField(null=True, blank=True)
    closes_at = models.TimeField(null=True, blank=True)
    operating_hours = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. 08:00 AM - 10:00 PM",
    )
    domains_catered = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated, e.g. UPSC,SSC,NEET",
    )

    class Meta:
        verbose_name_plural = "libraries"

    def __str__(self):
        return self.name

    @property
    def domains_list(self):
        if not self.domains_catered:
            return []
        return [d.strip() for d in self.domains_catered.split(",") if d.strip()]


class PricingPlan(BaseModel):
    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    name = models.CharField(max_length=50)  # e.g. "Monthly"
    duration_days = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["duration_days", "price"]

    def __str__(self):
        return f"{self.library.name} - {self.name} (₹{self.price})"
