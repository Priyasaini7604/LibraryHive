from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.libraries.models import Library, Seat, PricingPlan


class Membership(BaseModel):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("due", "Due"),
        ("overdue", "Overdue"),
        ("archived", "Archived"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.PROTECT,
        related_name="memberships",
    )

    start_date = models.DateField()

    next_due_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    def __str__(self):
        return f"{self.student.name} - {self.library.name} - {self.status}"