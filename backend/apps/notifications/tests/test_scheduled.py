"""Scheduled steps and the orchestrator: idempotent milestones, summaries, email retry, failure isolation, trigger."""

import io
import json
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core import jobs
from apps.core.dates import business_today
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications import scheduled, senders
from apps.notifications.models import Notification, NotificationDelivery
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for


def shift(membership, *, due_in):
    due = business_today() + timedelta(days=due_in)
    Membership.objects.filter(pk=membership.pk).update(start_date=due - timedelta(days=30), next_due_date=due)


class JobBase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.members = {}
        for index, (name, due_in) in enumerate((("far", 20), ("soon", 2), ("today", 0), ("late", -3))):
            member = make_membership(
                library=self.library,
                plan=self.plan,
                student=make_student(),
                seat=self.seats[index % 3] if index < 3 else None,
            )
            shift(member, due_in=due_in)
            self.members[name] = member


class RenewalNotificationTests(JobBase):
    def test_creates_one_notification_per_milestone(self):
        summary = scheduled.renewal_notifications()
        self.assertEqual(summary, {"due_soon": 1, "due_today": 1, "overdue": 1, "created": 3})
        kinds = {n.recipient_id: n.type for n in Notification.objects.exclude(type__in=["payment_received"])}
        self.assertEqual(kinds[self.members["soon"].student_id], "renewal_due_soon")
        self.assertEqual(kinds[self.members["today"].student_id], "renewal_due_today")
        self.assertEqual(kinds[self.members["late"].student_id], "membership_overdue")
        self.assertNotIn(self.members["far"].student_id, kinds)

    def test_keys_follow_the_spec(self):
        scheduled.renewal_notifications()
        note = Notification.objects.get(recipient=self.members["soon"].student)
        member = self.members["soon"]
        due = business_today() + timedelta(days=2)
        self.assertEqual(note.dedup_key, f"renewal:{member.pk}:due_soon:{due}:{member.student_id}")

    def test_running_five_times_creates_no_duplicates_and_no_extra_emails(self):
        for _ in range(5):
            scheduled.renewal_notifications()
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(NotificationDelivery.objects.count(), 3)

    def test_a_renewed_member_is_reminded_again_for_the_next_due_date(self):
        scheduled.renewal_notifications()
        late = self.members["late"]
        shift(late, due_in=-1)  # a different due date is a different milestone key
        scheduled.renewal_notifications()
        self.assertEqual(Notification.objects.filter(recipient=late.student).count(), 2)

    def test_archived_members_are_never_reminded(self):
        Membership.objects.filter(pk=self.members["late"].pk).update(state="archived", archived_at=timezone.now())
        self.assertEqual(scheduled.renewal_notifications()["created"], 2)


class OwnerSummaryTests(JobBase):
    def test_one_summary_per_library_per_day(self):
        first = scheduled.owner_summaries()
        self.assertEqual(first, {"libraries": 1, "created": 1})
        for _ in range(4):
            self.assertEqual(scheduled.owner_summaries()["created"], 0)
        note = Notification.objects.get(recipient=self.library.owner)
        self.assertEqual(note.type, "owner_daily_dues_summary")
        self.assertEqual(note.dedup_key, f"owner_dues:{self.library.pk}:{business_today()}")
        self.assertIn("2 member(s) are due and 1 are overdue", note.body)

    def test_a_new_day_gets_a_new_summary_and_quiet_libraries_get_none(self):
        scheduled.owner_summaries()
        tomorrow = business_today() + timedelta(days=1)
        self.assertEqual(scheduled.owner_summaries(today=tomorrow)["created"], 1)
        other, other_plan, other_seats = bookable_library()
        make_membership(library=other, plan=other_plan, seat=other_seats[0])  # due in 30 days: not due
        self.assertEqual(scheduled.owner_summaries()["libraries"], 1)
        self.assertFalse(Notification.objects.filter(recipient=other.owner).exists())


class EmailTests(JobBase):
    class Recorder:
        def __init__(self, fail=False):
            self.fail, self.sent = fail, []

        def send(self, *, to, subject, body):
            if self.fail:
                raise ConnectionError("smtp down")
            self.sent.append(to)
            return "<id@libraryhive>"

    def test_sends_pending_emails_once(self):
        scheduled.renewal_notifications()
        recorder = self.Recorder()
        with mock.patch.object(senders, "get_sender", return_value=recorder):
            first = scheduled.send_emails()
            second = scheduled.send_emails()
        self.assertEqual((first["attempted"], first["sent"]), (3, 3))
        self.assertEqual(second["attempted"], 0)
        self.assertEqual(len(recorder.sent), 3)

    def test_failures_back_off_and_stop_after_five_attempts(self):
        scheduled.renewal_notifications()
        broken = self.Recorder(fail=True)
        now = timezone.now()
        with mock.patch.object(senders, "get_sender", return_value=broken):
            self.assertEqual(scheduled.send_emails(now=now)["failed"], 3)
            self.assertEqual(scheduled.send_emails(now=now + timedelta(minutes=5))["attempted"], 0)  # still backing off
            later = now
            for minutes in (16, 31, 61, 121):
                later = later + timedelta(minutes=minutes)
                self.assertEqual(scheduled.send_emails(now=later)["attempted"], 3)
            self.assertEqual(scheduled.send_emails(now=later + timedelta(days=2))["attempted"], 0)
        delivery = NotificationDelivery.objects.first()
        self.assertEqual((delivery.status, delivery.attempts), ("failed", 5))

    def test_disabled_by_setting(self):
        scheduled.renewal_notifications()
        with override_settings(EMAIL_NOTIFICATIONS_ENABLED=False):
            self.assertEqual(scheduled.send_emails()["disabled"], 1)


class OrchestratorTests(JobBase):
    def run_all(self, **kwargs):
        return jobs.run_steps(**kwargs)

    def test_runs_every_step_in_order_and_five_runs_create_one_set_of_notifications(self):
        for _ in range(5):
            summary = self.run_all()
        self.assertTrue(summary["ok"])
        self.assertEqual([s["name"] for s in summary["steps"]], list(jobs.STEP_NAMES))
        self.assertEqual(Notification.objects.filter(type__startswith="renewal").count(), 2)
        self.assertEqual(Notification.objects.filter(type="membership_overdue").count(), 1)
        self.assertEqual(Notification.objects.filter(type="owner_daily_dues_summary").count(), 1)

    def test_only_selects_steps_and_rejects_unknown_names(self):
        summary = self.run_all(only=["renewal_notifications"])
        self.assertEqual([s["name"] for s in summary["steps"]], ["renewal_notifications"])
        with self.assertRaises(ValueError):
            self.run_all(only=["nope"])

    def test_a_failing_step_does_not_stop_the_later_ones(self):
        def boom():
            raise RuntimeError("database hiccup")

        broken = (jobs.Step("reconcile_payments", boom),)
        steps = tuple(broken if s.name == "reconcile_payments" else s for s in jobs.STEPS)
        steps = tuple(s[0] if isinstance(s, tuple) else s for s in steps)
        with mock.patch.object(jobs, "STEPS", steps):
            summary = self.run_all()
        self.assertFalse(summary["ok"])
        by_name = {s["name"]: s for s in summary["steps"]}
        self.assertFalse(by_name["reconcile_payments"]["ok"])
        self.assertIn("database hiccup", by_name["reconcile_payments"]["error"])
        self.assertTrue(by_name["renewal_notifications"]["ok"])
        self.assertEqual(Notification.objects.filter(type="membership_overdue").count(), 1)

    def test_dry_run_reports_figures_but_saves_and_sends_nothing(self):
        summary = self.run_all(dry_run=True)
        by_name = {s["name"]: s for s in summary["steps"]}
        self.assertEqual(by_name["renewal_notifications"]["created"], 3)
        self.assertEqual(by_name["send_emails"]["skipped"], "dry run")
        self.assertFalse(Notification.objects.exists())

    def test_the_command_prints_a_summary_and_fails_on_a_failed_step(self):
        out = io.StringIO()
        call_command("run_scheduled_jobs", "--only", "owner_summaries", stdout=out)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        call_command("run_scheduled_jobs", "--dry-run", stdout=io.StringIO())

        def boom():
            raise RuntimeError("x")

        with mock.patch.object(jobs, "STEPS", (jobs.Step("expire_holds", boom),)), self.assertRaises(CommandError):
            call_command("run_scheduled_jobs", "--only", "expire_holds", stdout=io.StringIO())

    def test_expired_holds_and_stale_orders_are_handled_by_the_job(self):
        fresh = make_student()
        Membership.objects.filter(pk=self.members["far"].pk).update(state="archived", archived_at=timezone.now())
        hold = self.hold_seat(student=fresh, seat=self.seats[0])
        self.expire(hold)
        summary = self.run_all(only=["expire_holds"])
        self.assertEqual(summary["steps"][0]["expired"], 1)


class TriggerEndpointTests(JobBase):
    URL = "/api/v1/internal/jobs/run/"

    def test_disabled_without_a_configured_token(self):
        with override_settings(JOB_TRIGGER_TOKEN=""):
            response = APIClient().post(self.URL, HTTP_X_JOB_TOKEN="anything")
        self.assertEqual(response.status_code, 404)

    def test_wrong_or_missing_token_is_refused_and_runs_nothing(self):
        with override_settings(JOB_TRIGGER_TOKEN="s3cret-token-value"):
            self.assertEqual(APIClient().post(self.URL).status_code, 403)
            self.assertEqual(APIClient().post(self.URL, HTTP_X_JOB_TOKEN="wrong").status_code, 403)
            self.assertEqual(client_for(self.library.owner).post(self.URL).status_code, 403)  # a login is not a token
        self.assertFalse(Notification.objects.exists())

    def test_the_right_token_runs_the_jobs(self):
        with override_settings(JOB_TRIGGER_TOKEN="s3cret-token-value"):
            response = APIClient().post(self.URL, HTTP_X_JOB_TOKEN="s3cret-token-value")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["steps"]), len(jobs.STEPS))
        self.assertEqual(Notification.objects.filter(type="membership_overdue").count(), 1)
