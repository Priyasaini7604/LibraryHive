"""Email delivery of notifications (NOT-07, NOT-08, BACKEND_ARCHITECTURE.md 11.3).

`send_delivery()` sends one delivery row and records the outcome. The scheduled
job (T24) loops over `selectors.due_deliveries()` and calls it; this module
owns the per-row state machine and the retry rules:

- pending or failed rows are attempted at most `MAX_ATTEMPTS` (5) times;
- after a failure the next attempt is `15 minutes x 2^(failed attempts - 1)`
  later (15, 30, 60, 120), and after the fifth failure the row stays `failed`;
- a row is locked while it is sent (`skip_locked`), so two overlapping runs
  cannot both send it. A crash between sending and saving can re-send one
  email once: accepted at-least-once behaviour (SPEC.md 4.5).
"""

import logging
from datetime import timedelta
from email.utils import make_msgid
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import NotificationDelivery

logger = logging.getLogger("apps.notifications")

BACKOFF_BASE = timedelta(minutes=15)
ERROR_MAX = 500


class EmailSender(Protocol):
    """Anything that can deliver one plain-text email and return the provider's message id."""

    def send(self, *, to: str, subject: str, body: str) -> str: ...


class DjangoEmailSender:
    """Uses Django's configured EMAIL_BACKEND: console locally, the provider's backend in production."""

    def send(self, *, to: str, subject: str, body: str) -> str:
        message_id = make_msgid(domain="libraryhive")
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
            headers={"Message-ID": message_id},
        ).send(fail_silently=False)
        return message_id[:120]


def get_sender() -> EmailSender:
    return DjangoEmailSender()


def backoff_after(failed_attempts: int) -> timedelta:
    """Delay before the next try once `failed_attempts` attempts have failed: 15, 30, 60, 120 minutes."""
    return BACKOFF_BASE * (2 ** (failed_attempts - 1))


def send_delivery(delivery_id, *, sender: EmailSender | None = None, now=None) -> str | None:
    """Attempt one delivery if it is due. Returns its status, or None if another run holds it or it is gone."""
    now = now or timezone.now()
    sender = sender or get_sender()
    with transaction.atomic():
        delivery = (
            NotificationDelivery.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("notification__recipient")
            .filter(pk=delivery_id)
            .first()
        )
        if delivery is None:
            return None
        retryable = delivery.status in (NotificationDelivery.Status.PENDING, NotificationDelivery.Status.FAILED)
        due = delivery.next_attempt_at is None or delivery.next_attempt_at <= now
        if not retryable or delivery.attempts >= NotificationDelivery.MAX_ATTEMPTS or not due:
            return delivery.status

        notification = delivery.notification
        recipient = notification.recipient
        if not recipient.email:
            delivery.status = NotificationDelivery.Status.SKIPPED
            delivery.last_error = "Recipient has no email address."
            delivery.save(update_fields=["status", "last_error", "updated_at"])
            return delivery.status

        body = render_to_string(
            "notifications/email/notification.txt", {"name": recipient.name, "body": notification.body}
        )
        delivery.attempts += 1
        try:
            delivery.provider_message_id = sender.send(to=recipient.email, subject=notification.title, body=body)
        except Exception as exc:
            delivery.status = NotificationDelivery.Status.FAILED
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:ERROR_MAX]
            exhausted = delivery.attempts >= NotificationDelivery.MAX_ATTEMPTS
            delivery.next_attempt_at = None if exhausted else now + backoff_after(delivery.attempts)
            logger.warning(
                "Notification email failed",
                extra={"delivery_id": str(delivery.pk), "attempts": delivery.attempts, "gave_up": exhausted},
            )
        else:
            delivery.status = NotificationDelivery.Status.SENT
            delivery.sent_at = now
            delivery.next_attempt_at = None
            delivery.last_error = ""
            logger.info("Notification email sent", extra={"delivery_id": str(delivery.pk)})
        delivery.save()
        return delivery.status
