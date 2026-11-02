"""Job steps owned by notifications (BACKEND_ARCHITECTURE.md 11, SPEC.md 4.5): milestones, owner summaries, email.

Every notification carries its deterministic `dedup_key`, so running a step any number of times creates no
duplicate (NOT-06). "Today" is the Asia/Kolkata business date.
"""

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.dates import business_today
from apps.memberships.models import Membership

from . import senders, services
from .models import Notification, NotificationDelivery
from .services import NotificationSpec

logger = logging.getLogger("apps.notifications")

DUE_SOON = "due_soon"
DUE_TODAY = "due_today"
OVERDUE = "overdue"


def _notify_isolated(specs: list[NotificationSpec]) -> tuple[int, int, int]:
    """Create notifications so that one bad row cannot stop the others: `(created, skipped, failed)`.

    The whole batch goes in one insert first. If that raises, each notification is retried on its own, so only
    the genuinely failing ones are counted as failed. `skipped` are keys that already exist (an earlier run or
    a repeat), which is the normal outcome of a re-run, not a problem.
    """
    unique = list({spec.dedup_key: spec for spec in specs}.values())
    if not unique:
        return 0, 0, 0
    try:
        created = services.notify_many(unique)
    except Exception:
        logger.exception("Notification batch failed; retrying one by one", extra={"batch_size": len(unique)})
    else:
        return len(created), len(unique) - len(created), 0
    created_count = skipped = failed = 0
    for spec in unique:
        try:
            made = services.notify_many([spec])
        except Exception:
            failed += 1
            logger.exception("Notification failed", extra={"dedup_key": spec.dedup_key})
        else:
            if made:
                created_count += 1
            else:
                skipped += 1
    return created_count, skipped, failed


def _membership_spec(membership: Membership, milestone: str) -> NotificationSpec:
    """The student's renewal reminder. Key: `renewal:{membership_id}:{milestone}:{due_date}:{recipient_id}`."""
    library = membership.library.name
    when = f"{membership.next_due_date:%d %b %Y}"
    kind, title, body = {
        DUE_SOON: (
            Notification.Type.RENEWAL_DUE_SOON,
            "Your membership is due soon",
            f"Your membership at {library} is due on {when}. Renew to keep seat {membership.seat.label}.",
        ),
        DUE_TODAY: (
            Notification.Type.RENEWAL_DUE_TODAY,
            "Your membership is due today",
            f"Your membership at {library} is due today ({when}). Renew to keep seat {membership.seat.label}.",
        ),
        OVERDUE: (
            Notification.Type.MEMBERSHIP_OVERDUE,
            "Your membership is overdue",
            f"Your membership at {library} was due on {when}. Please renew to keep seat {membership.seat.label}.",
        ),
    }[milestone]
    return NotificationSpec(
        recipient=membership.student,
        type=kind,
        title=title,
        body=body,
        dedup_key=f"renewal:{membership.pk}:{milestone}:{membership.next_due_date}:{membership.student_id}",
        entity=("membership", membership.pk),
    )


def renewal_notifications(*, today: date | None = None) -> dict[str, int]:
    """Remind students 3 days before, on, and after their due date (one notification per milestone and due date).

    A member whose due date is within the next 3 days gets `due_soon` once, even if the job missed the exact day.
    Archived memberships are never reminded.
    """
    today = today or business_today()
    window = today + timedelta(days=settings.MEMBERSHIP_DUE_WINDOW_DAYS)
    live = Membership.objects.filter(state=Membership.State.ACTIVE).select_related("student", "library", "seat")
    groups = {
        DUE_SOON: live.filter(next_due_date__gt=today, next_due_date__lte=window),
        DUE_TODAY: live.filter(next_due_date=today),
        OVERDUE: live.filter(next_due_date__lt=today),
    }
    candidates: dict[str, int] = {}
    created = skipped = errors = 0
    for milestone, queryset in groups.items():
        # Each milestone is isolated: a failure in one group (or one member) never stops the others.
        try:
            found = list(queryset)
        except Exception:
            logger.exception("Could not load memberships", extra={"milestone": milestone})
            candidates[milestone] = 0
            errors += 1
            continue
        candidates[milestone] = len(found)
        specs: list[NotificationSpec] = []
        for membership in found:
            try:
                specs.append(_membership_spec(membership, milestone))
            except Exception:
                errors += 1
                logger.exception(
                    "Could not build a reminder", extra={"milestone": milestone, "membership_id": str(membership.pk)}
                )
        made, already, failed = _notify_isolated(specs)
        created, skipped, errors = created + made, skipped + already, errors + failed
    summary = {**candidates, "created": created, "skipped": skipped, "processing_errors": errors}
    # `created` is reserved by the logging module, so the log line uses another name.
    logger.info(
        "Renewal notifications",
        extra={**candidates, "inserted": created, "skipped": skipped, "processing_errors": errors},
    )
    return summary


def owner_summaries(*, today: date | None = None) -> dict[str, int]:
    """Tell each owner once a day how many members are due and overdue. Key: `owner_dues:{library_id}:{date}`."""
    today = today or business_today()
    window = today + timedelta(days=settings.MEMBERSHIP_DUE_WINDOW_DAYS)
    rows = (
        Membership.objects.filter(state=Membership.State.ACTIVE, next_due_date__lte=window)
        .values("library_id", "library__name", "library__owner_id")
        .annotate(
            overdue=Count("id", filter=Q(next_due_date__lt=today)), due=Count("id", filter=~Q(next_due_date__lt=today))
        )
    )
    from apps.accounts.models import User

    owners = {u.pk: u for u in User.objects.filter(pk__in=[r["library__owner_id"] for r in rows])}
    specs: list[NotificationSpec] = []
    errors = 0
    for row in rows:
        try:
            specs.append(
                NotificationSpec(
                    recipient=owners[row["library__owner_id"]],
                    type=Notification.Type.OWNER_DAILY_DUES_SUMMARY,
                    title="Today's dues",
                    body=f"{row['due']} member(s) are due and {row['overdue']} are overdue at {row['library__name']}.",
                    dedup_key=f"owner_dues:{row['library_id']}:{today}",
                    entity=("library", row["library_id"]),
                )
            )
        except Exception:
            errors += 1
            logger.exception("Could not build an owner summary", extra={"library_id": str(row["library_id"])})
    created, skipped, failed = _notify_isolated(specs)
    errors += failed
    logger.info(
        "Owner summaries",
        extra={"libraries": len(specs), "inserted": created, "skipped": skipped, "processing_errors": errors},
    )
    return {"libraries": len(specs), "created": created, "skipped": skipped, "processing_errors": errors}


def send_emails(*, limit: int = 200, now=None) -> dict[str, int]:
    """Try every due pending or failed email delivery once (backoff and the 5-attempt cap live in `send_delivery`)."""
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0, "disabled": 1}
    now = now or timezone.now()
    ids = list(
        NotificationDelivery.objects.filter(
            status__in=[NotificationDelivery.Status.PENDING, NotificationDelivery.Status.FAILED],
            attempts__lt=NotificationDelivery.MAX_ATTEMPTS,
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
    outcome = {"attempted": len(ids), "sent": 0, "failed": 0, "skipped": 0}
    for delivery_id in ids:
        status = senders.send_delivery(delivery_id, now=now)
        if status in outcome:
            outcome[status] += 1
    return outcome
