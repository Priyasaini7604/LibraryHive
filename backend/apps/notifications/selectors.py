"""Read-side queries for notifications."""

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Notification, NotificationDelivery


def inbox(user, *, unread_only: bool = False) -> QuerySet[Notification]:
    """The user's own notifications, newest first (#58). Never anyone else's."""
    queryset = Notification.objects.filter(recipient=user)
    return queryset.filter(read_at__isnull=True) if unread_only else queryset


def unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def due_deliveries(*, now=None) -> QuerySet[NotificationDelivery]:
    """Email deliveries the scheduled job should attempt now: pending or failed, under the attempt limit, and due."""
    now = now or timezone.now()
    return NotificationDelivery.objects.filter(
        status__in=[NotificationDelivery.Status.PENDING, NotificationDelivery.Status.FAILED],
        attempts__lt=NotificationDelivery.MAX_ATTEMPTS,
    ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
