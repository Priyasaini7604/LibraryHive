from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.libraries.models import Library, PricingPlan
from apps.seats.models import Seat

class Booking(BaseModel):

    STATUS_CHOICES = (
        ("reserved", "Reserved"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="reserved",
    )

    reserved_until = models.DateTimeField()

    def __str__(self):
        return f"{self.student.name} - {self.library.name} - {self.seat.label}"