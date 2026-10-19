"""The scheduled-job orchestrator (BACKEND_ARCHITECTURE.md 11, AGENTS.md 6).

One idempotent entry point runs every step in order: `manage.py run_scheduled_jobs`, run hourly by the host's
cron, or the token-protected `POST /api/v1/internal/jobs/run/` as a fallback. A step that fails is recorded and
the later steps still run. Steps are imported when they run, so `core` never depends on the other apps at load.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from django.db import transaction

logger = logging.getLogger("apps.core")


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable[[], dict]
    #: Steps that talk to the outside world (email) are skipped in a dry run.
    external: bool = False


def _expire_holds() -> dict:
    from apps.seats import services

    return {"expired": services.expire_dead_holds()}


def _reconcile_payments() -> dict:
    from apps.payments import services

    return services.reconcile_stale_orders()


def _auto_close_attendance() -> dict:
    from apps.attendance import services

    return services.auto_close_open_records()


def _renewal_notifications() -> dict:
    from apps.notifications import scheduled

    return scheduled.renewal_notifications()


def _owner_summaries() -> dict:
    from apps.notifications import scheduled

    return scheduled.owner_summaries()


def _send_emails() -> dict:
    from apps.notifications import scheduled

    return scheduled.send_emails()


# Order matters: expire and settle first, notify next, and send email last so new notifications go out in the same run.
STEPS: tuple[Step, ...] = (
    Step("expire_holds", _expire_holds),
    Step("reconcile_payments", _reconcile_payments),
    Step("auto_close_attendance", _auto_close_attendance),
    Step("renewal_notifications", _renewal_notifications),
    Step("owner_summaries", _owner_summaries),
    Step("send_emails", _send_emails, external=True),
)

STEP_NAMES = tuple(step.name for step in STEPS)


class DryRunRollback(Exception):
    """Raised inside the dry-run transaction to undo everything a step wrote."""


def run_steps(*, only: list[str] | None = None, dry_run: bool = False) -> dict:
    """Run the selected steps and return `{ok, dry_run, steps: [{name, ok, ...figures or error}]}`.

    A dry run executes each database step inside a transaction that is rolled back, so the figures show what
    would happen while nothing is saved; external steps are reported as skipped.
    """
    unknown = sorted(set(only or []) - set(STEP_NAMES))
    if unknown:
        raise ValueError(f"Unknown step(s): {', '.join(unknown)}. Choose from: {', '.join(STEP_NAMES)}.")
    results = []
    for step in STEPS:
        if only and step.name not in only:
            continue
        started = time.monotonic()
        if dry_run and step.external:
            results.append({"name": step.name, "ok": True, "skipped": "dry run"})
            continue
        try:
            if dry_run:
                try:
                    with transaction.atomic():
                        figures = step.run()
                        raise DryRunRollback
                except DryRunRollback:
                    pass
            else:
                figures = step.run()
            results.append({"name": step.name, "ok": True, **figures, "seconds": round(time.monotonic() - started, 2)})
        except Exception as exc:  # one failing step must not stop the later ones
            logger.exception("Scheduled step failed", extra={"step": step.name})
            results.append({"name": step.name, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})
    summary = {"ok": all(r["ok"] for r in results), "dry_run": dry_run, "steps": results}
    logger.info("Scheduled jobs finished", extra={"ok": summary["ok"], "dry_run": dry_run})
    return summary
