"""Creating and reading notifications (BACKEND_ARCHITECTURE.md 11.2, SPEC.md 3.13, 4.5).

Every other app calls `notify()` from inside its own transaction. The insert
uses `ON CONFLICT (dedup_key) DO NOTHING`, so replaying an event or re-running
a job never creates a second notification.
"""

import logging
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import NotFound

from .models import Notification, NotificationDelivery

logger = logging.getLogger("apps.notifications")

TITLE_MAX = 150
BODY_MAX = 1000
DEDUP_KEY_MAX = 200


@dataclass(frozen=True)
class NotificationSpec:
    """One notification to create. `entity` is the deep-link target as (entity_type, id)."""

    recipient: object
    type: str
    title: str
    body: str
    dedup_key: str
    entity: tuple[str, uuid.UUID] | None = None


def _fit(text: str, limit: int) -> str:
    """Notifications must never break the caller's business transaction, so oversize text is cut, not rejected."""
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _build(spec: NotificationSpec) -> Notification:
    if spec.type not in Notification.Type.values:
        raise ValueError(f"Unknown notification type: {spec.type!r}")
    if not spec.dedup_key or len(spec.dedup_key) > DEDUP_KEY_MAX:
        raise ValueError(f"dedup_key must be 1-{DEDUP_KEY_MAX} characters.")
    entity_type, entity_id = spec.entity if spec.entity else (None, None)
    return Notification(
        recipient=spec.recipient,
        type=spec.type,
        title=_fit(spec.title, TITLE_MAX),
        body=_fit(spec.body, BODY_MAX),
        entity_type=entity_type,
        entity_id=entity_id,
        dedup_key=spec.dedup_key,
    )


def _delivery_for(notification: Notification) -> NotificationDelivery | None:
    """The email delivery row for a new notification, or None when email is switched off.

    A recipient without an email address gets a `skipped` row so the log says why nothing was sent.
    """
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return None
    if notification.recipient.email:
        return NotificationDelivery(notification=notification, status=NotificationDelivery.Status.PENDING)
    return NotificationDelivery(notification=notification, status=NotificationDelivery.Status.SKIPPED)


@transaction.atomic
def notify_many(specs: list[NotificationSpec]) -> list[Notification]:
    """Create many notifications in one insert. Returns only the ones actually created.

    Keys that already exist (or repeat inside `specs`) are skipped silently. Delivery rows are created
    only for new notifications, so a replay can never queue a second email.
    """
    unique: dict[str, Notification] = {}
    for spec in specs:
        if spec.dedup_key not in unique:
            unique[spec.dedup_key] = _build(spec)
    if not unique:
        return []

    candidates = list(unique.values())
    Notification.objects.bulk_create(candidates, ignore_conflicts=True)
    # Primary keys are generated client-side, so a skipped (conflicting) row's key is not in the table.
    inserted_ids = set(Notification.objects.filter(pk__in=[n.pk for n in candidates]).values_list("pk", flat=True))
    created = [n for n in candidates if n.pk in inserted_ids]

    deliveries = [d for d in (_delivery_for(n) for n in created) if d is not None]
    NotificationDelivery.objects.bulk_create(deliveries, ignore_conflicts=True)

    logger.info(
        "Notifications created",
        extra={"requested": len(specs), "created": len(created), "duplicates": len(unique) - len(created)},
    )
    return created


def notify(
    *,
    recipient,
    type: str,
    title: str,
    body: str,
    dedup_key: str,
    entity: tuple[str, uuid.UUID] | None = None,
) -> Notification | None:
    """Create one notification. Returns it, or None if `dedup_key` already exists (a replay)."""
    created = notify_many(
        [NotificationSpec(recipient=recipient, type=type, title=title, body=body, dedup_key=dedup_key, entity=entity)]
    )
    return created[0] if created else None


def mark_read(*, user, notification_id) -> Notification:
    """Mark one of the user's own notifications read (#60). Idempotent: the first read time is kept.

    Someone else's notification is simply not found (404), never confirmed to exist.
    """
    Notification.objects.filter(pk=notification_id, recipient=user, read_at__isnull=True).update(
        read_at=timezone.now(), updated_at=timezone.now()
    )
    try:
        return Notification.objects.get(pk=notification_id, recipient=user)
    except (Notification.DoesNotExist, ValueError) as exc:
        raise NotFound() from exc


def mark_all_read(*, user) -> int:
    """Mark every unread notification of the user read (#61). Returns how many changed."""
    now = timezone.now()
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(read_at=now, updated_at=now)
