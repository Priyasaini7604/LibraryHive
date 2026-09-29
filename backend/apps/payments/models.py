from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.bookings.models import Booking


class Payment(BaseModel):

    METHOD_CHOICES = (
        ("razorpay", "Razorpay"),
        ("cash", "Cash"),
        ("upi", "UPI"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("successful", "Successful"),
        ("failed", "Failed"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default="razorpay",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    razorpay_signature = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.student.name} - ₹{self.amount} - {self.status}"