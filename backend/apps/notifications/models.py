from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel


class Notification(BaseModel):
    """One in-app notification for one recipient (SPEC.md 3.13).

    `dedup_key` is built deterministically by whoever creates the notification
    (SPEC.md 4.5) and is unique, so re-running a job or replaying an event can
    never create a second row (NOT-06). Rows are only created through
    `notifications.services.notify()`.

    The `library` scope column is added together with the Library model (T08),
    the same way `AuditLog.library` is. Notifications are read by recipient
    only, so no API here depends on it.
    """

    class Type(models.TextChoices):
        RENEWAL_DUE_SOON = "renewal_due_soon", "Renewal due soon"
        RENEWAL_DUE_TODAY = "renewal_due_today", "Renewal due today"
        MEMBERSHIP_OVERDUE = "membership_overdue", "Membership overdue"
        OWNER_DAILY_DUES_SUMMARY = "owner_daily_dues_summary", "Daily dues summary"
        BOOKING_CONFIRMED = "booking_confirmed", "Booking confirmed"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        PAYMENT_NEEDS_REFUND = "payment_needs_refund", "Payment needs refund"
        COMPLAINT_CREATED = "complaint_created", "Complaint created"
        COMPLAINT_UPDATED = "complaint_updated", "Complaint updated"
        VISIT_REQUESTED = "visit_requested", "Visit requested"
        VISIT_DECIDED = "visit_decided", "Visit decided"
        ACCOUNT_CLAIMED = "account_claimed", "Account claimed"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    type = models.CharField(max_length=40, choices=Type.choices)
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=1000)
    entity_type = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001 - SPEC 3.13 (N)
    entity_id = models.UUIDField(null=True, blank=True)
    dedup_key = models.CharField(max_length=200)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"], name="notification_inbox_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["dedup_key"], name="notification_dedup_key_unique"),
        ]

    def __str__(self):
        return f"{self.type} -> {self.recipient_id}"


class NotificationDelivery(BaseModel):
    """Email delivery state of one notification (SPEC.md 3.14, NOT-07). In-app needs no row."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    MAX_ATTEMPTS = 5

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    provider_message_id = models.CharField(max_length=120, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="delivery_status_next_idx")]
        constraints = [
            models.UniqueConstraint(fields=["notification", "channel"], name="delivery_notification_channel_unique"),
            models.CheckConstraint(condition=Q(attempts__lte=5), name="delivery_max_attempts"),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "sent", "failed", "skipped"]), name="delivery_status_valid"
            ),
        ]

    def __str__(self):
        return f"{self.channel} {self.status} ({self.notification_id})"
