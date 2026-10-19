"""Run every scheduled step once: `python manage.py run_scheduled_jobs` (hourly from the host's cron).

Idempotent: running it again changes nothing that already happened. Exit status is non-zero if any step failed.
"""

import json

from django.core.management.base import BaseCommand, CommandError

from apps.core import jobs


class Command(BaseCommand):
    help = "Expire holds, reconcile payments, close attendance, send reminders and email. Safe to run repeatedly."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            action="append",
            choices=jobs.STEP_NAMES,
            help="Run only this step (repeat the option for several).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what each database step would do, save nothing and send no email.",
        )

    def handle(self, *args, only=None, dry_run=False, **options):
        summary = jobs.run_steps(only=only, dry_run=dry_run)
        self.stdout.write(json.dumps(summary, default=str, indent=2))
        if not summary["ok"]:
            failed = [s["name"] for s in summary["steps"] if not s["ok"]]
            raise CommandError(f"Step(s) failed: {', '.join(failed)}")
