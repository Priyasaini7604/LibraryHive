"""Read-side queries for notifications."""

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone

from config.settings.guard import NON_DELIVERING_EMAIL_BACKENDS

from .models import Notification, NotificationDelivery


def inbox(user, *, unread_only: bool = False) -> QuerySet[Notification]:
    """The user's own notifications, newest first (#58). Never anyone else's."""
    queryset = Notification.objects.filter(recipient=user)
    return queryset.filter(read_at__isnull=True) if unread_only else queryset


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def email_delivery_active() -> bool:
    """True only when an email would really leave the server: the switch is on and the backend delivers.

    The console, locmem, dummy and file backends accept a message without sending it, so they never count.
    """
    return settings.EMAIL_NOTIFICATIONS_ENABLED and settings.EMAIL_BACKEND not in NON_DELIVERING_EMAIL_BACKENDS


def due_deliveries(*, now=None) -> QuerySet[NotificationDelivery]:
    """Email deliveries the scheduled job should attempt now: pending or failed, under the attempt limit, and due."""
    now = now or timezone.now()
    return NotificationDelivery.objects.filter(
        status__in=[NotificationDelivery.Status.PENDING, NotificationDelivery.Status.FAILED],
        attempts__lt=NotificationDelivery.MAX_ATTEMPTS,
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
