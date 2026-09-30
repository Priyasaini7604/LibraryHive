from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.libraries.models import Library
from apps.memberships.models import Membership


class Notification(BaseModel):
    TYPE_CHOICES = (
        ("renewal_upcoming", "Renewal Upcoming"),
        ("payment_due", "Payment Due"),
        ("payment_overdue", "Payment Overdue"),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    membership = models.ForeignKey(
        Membership,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
    )

    title = models.CharField(
        max_length=255,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient.email} - {self.title}"