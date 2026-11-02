"""Reliability of the scheduled notification and attendance steps run from GitHub Actions.

The scheduler only calls `manage.py run_scheduled_jobs --only <step>`; everything it relies on is tested here:
IST date boundaries, a workflow that runs twice, parallel runs, partial failures, and email that is switched off.
No message is ever sent: the test settings use the in-memory email backend and no external call is made.
"""

import io
import json
import threading
from datetime import UTC, date, datetime, time, timedelta
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.attendance import services as attendance
from apps.attendance.models import AttendanceRecord
from apps.attendance.tests.test_attendance import AttendanceBase
from apps.core import jobs
from apps.core.dates import business_today
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications import scheduled, services
from apps.notifications.models import Notification, NotificationDelivery
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for

from .test_scheduled import JobBase

DAILY = ("renewal_notifications", "owner_summaries")


def at_utc(year, month, day, hour, minute):
    """Freeze the clock at an exact UTC instant (the business date is then derived in Asia/Kolkata)."""
    return mock.patch("django.utils.timezone.now", return_value=datetime(year, month, day, hour, minute, tzinfo=UTC))


def run_command(*steps) -> dict:
    """Run the management command exactly as the workflow does and return its JSON summary."""
    out = io.StringIO()
    args = [arg for step in steps for arg in ("--only", step)]
    call_command("run_scheduled_jobs", *args, stdout=out)
    return json.loads(out.getvalue())


def step_figures(summary: dict, name: str) -> dict:
    return next(step for step in summary["steps"] if step["name"] == name)


class IstBoundaryTests(PaymentTestCase):
    """The business date is the Asia/Kolkata date, which is already tomorrow for the last 5.5 hours of the UTC day."""

    def due_member(self, due: date, seat):
        member = make_membership(library=self.library, plan=self.plan, student=make_student(), seat=seat)
        Membership.objects.filter(pk=member.pk).update(start_date=due - timedelta(days=30), next_due_date=due)
        return member

    def kinds(self):
        reminders = ("renewal_due_soon", "renewal_due_today", "membership_overdue")
        return {n.recipient_id: n.type for n in Notification.objects.filter(type__in=reminders)}

    def test_ist_is_already_the_next_day_in_the_last_hours_of_the_utc_day(self):
        with at_utc(2026, 11, 30, 18, 29):
            self.assertEqual(business_today(), date(2026, 11, 30))  # 23:59 IST
        with at_utc(2026, 11, 30, 18, 31):
            self.assertEqual(business_today(), date(2026, 12, 1))  # 00:01 IST, the UTC date is still 30 Nov
        with at_utc(2026, 12, 31, 18, 31):
            self.assertEqual(business_today(), date(2027, 1, 1))  # year end

    def test_milestones_just_before_and_just_after_ist_midnight_at_month_end(self):
        members = {
            "dec1": self.due_member(date(2026, 12, 1), self.seats[0]),
            "nov30": self.due_member(date(2026, 11, 30), self.seats[1]),
            "dec4": self.due_member(date(2026, 12, 4), self.seats[2]),
        }
        with at_utc(2026, 11, 30, 18, 29):  # 23:59 IST on 30 Nov
            scheduled.renewal_notifications()
            kinds = self.kinds()
            self.assertEqual(kinds[members["dec1"].student_id], "renewal_due_soon")
            self.assertEqual(kinds[members["nov30"].student_id], "renewal_due_today")
            self.assertNotIn(members["dec4"].student_id, kinds)  # four days away: no reminder yet
        Notification.objects.all().delete()
        with at_utc(2026, 11, 30, 18, 31):  # 00:01 IST on 1 Dec
            scheduled.renewal_notifications()
            kinds = self.kinds()
            self.assertEqual(kinds[members["dec1"].student_id], "renewal_due_today")
            self.assertEqual(kinds[members["nov30"].student_id], "membership_overdue")
            self.assertEqual(kinds[members["dec4"].student_id], "renewal_due_soon")  # exactly three days away

    def test_year_end_boundary(self):
        member = self.due_member(date(2027, 1, 1), self.seats[0])
        with at_utc(2026, 12, 31, 18, 31):  # 1 Jan in IST
            scheduled.renewal_notifications()
        note = Notification.objects.get(recipient=member.student)
        self.assertEqual(note.type, "renewal_due_today")

    def test_three_day_window_is_inclusive_and_four_days_is_too_early(self):
        three = self.due_member(business_today() + timedelta(days=3), self.seats[0])
        four = self.due_member(business_today() + timedelta(days=4), self.seats[1])
        scheduled.renewal_notifications()
        self.assertTrue(Notification.objects.filter(recipient=three.student, type="renewal_due_soon").exists())
        self.assertFalse(Notification.objects.filter(recipient=four.student).exists())

    def test_a_reminder_for_one_due_date_is_not_repeated_across_the_ist_midnight(self):
        member = self.due_member(date(2026, 12, 1), self.seats[0])
        with at_utc(2026, 11, 30, 18, 29):
            scheduled.renewal_notifications()
            scheduled.renewal_notifications()
        with at_utc(2026, 11, 30, 18, 31):
            scheduled.renewal_notifications()
            scheduled.renewal_notifications()
        types = sorted(Notification.objects.filter(recipient=member.student).values_list("type", flat=True))
        self.assertEqual(types, ["renewal_due_soon", "renewal_due_today"])  # one per milestone, never more

    def test_the_owner_summary_is_keyed_by_the_ist_date(self):
        self.due_member(date(2026, 12, 1), self.seats[0])
        with at_utc(2026, 11, 30, 18, 29):
            scheduled.owner_summaries()
        with at_utc(2026, 11, 30, 18, 31):
            scheduled.owner_summaries()
            scheduled.owner_summaries()
        keys = sorted(Notification.objects.filter(type="owner_daily_dues_summary").values_list("dedup_key", flat=True))
        self.assertEqual(keys, [f"owner_dues:{self.library.pk}:2026-11-30", f"owner_dues:{self.library.pk}:2026-12-01"])


class WorkflowRunsTwiceTests(JobBase):
    """The workflow may run twice (a retry, a manual run, a delayed schedule): nothing is created or sent twice."""

    def test_the_daily_command_twice_creates_each_notification_once(self):
        first = run_command(*DAILY)
        self.assertTrue(first["ok"])
        self.assertEqual(step_figures(first, "renewal_notifications")["created"], 3)
        self.assertEqual(step_figures(first, "owner_summaries")["created"], 1)
        total = Notification.objects.count()
        deliveries = NotificationDelivery.objects.count()

        second = run_command(*DAILY)
        self.assertTrue(second["ok"])
        figures = step_figures(second, "renewal_notifications")
        self.assertEqual((figures["created"], figures["skipped"], figures["processing_errors"]), (0, 3, 0))
        self.assertEqual(step_figures(second, "owner_summaries")["created"], 0)
        self.assertEqual((Notification.objects.count(), NotificationDelivery.objects.count()), (total, deliveries))
        self.assertEqual(mail.outbox, [])  # the daily steps never send email themselves

    def test_only_the_selected_steps_run(self):
        summary = run_command("renewal_notifications")
        self.assertEqual([step["name"] for step in summary["steps"]], ["renewal_notifications"])
        self.assertFalse(Notification.objects.filter(type="owner_daily_dues_summary").exists())

    def test_the_payment_step_is_not_part_of_the_scheduled_workflows(self):
        for steps in (DAILY, ("auto_close_attendance",)):
            names = [step["name"] for step in run_command(*steps)["steps"]]
            self.assertNotIn("reconcile_payments", names)
            self.assertNotIn("send_emails", names)


class ConcurrentRunTests(TransactionTestCase):
    """Overlapping runs (a manual run during a scheduled one) must not create a second notification."""

    def test_parallel_runs_create_each_notification_exactly_once(self):
        library, plan, seats = bookable_library(domain_codes=[], amenity_codes=[])
        for index, due_in in enumerate((2, 0, -3)):
            member = make_membership(library=library, plan=plan, student=make_student(), seat=seats[index])
            due = business_today() + timedelta(days=due_in)
            Membership.objects.filter(pk=member.pk).update(start_date=due - timedelta(days=30), next_due_date=due)

        workers = 6
        barrier = threading.Barrier(workers)
        created: list[int] = []
        errors: list[str] = []

        def worker():
            try:
                barrier.wait(timeout=15)
                renewal = scheduled.renewal_notifications()
                owner = scheduled.owner_summaries()
                created.append(renewal["created"] + owner["created"])
                if renewal["processing_errors"] or owner["processing_errors"]:
                    errors.append("processing error")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(repr(exc))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(errors, [])
        self.assertEqual(sum(created), 4)  # three reminders and one owner summary, created by exactly one run each
        self.assertEqual(Notification.objects.count(), 4)
        self.assertEqual(NotificationDelivery.objects.count(), 4)
        self.assertEqual(len({n.dedup_key for n in Notification.objects.all()}), 4)


class PartialFailureTests(JobBase):
    """One bad notification must not stop the others, must be visible, and must be retried by the next run."""

    def failing_spec_for(self, member):
        real = scheduled._membership_spec

        def build(membership, milestone):
            if membership.pk == member.pk:
                raise RuntimeError("cannot build this reminder")
            return real(membership, milestone)

        return mock.patch.object(scheduled, "_membership_spec", side_effect=build)

    def test_a_reminder_that_cannot_be_built_does_not_stop_the_others(self):
        with self.failing_spec_for(self.members["today"]):
            summary = scheduled.renewal_notifications()
        self.assertEqual((summary["created"], summary["processing_errors"]), (2, 1))
        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.members["soon"].student_id, self.members["late"].student_id})

    def test_the_step_is_reported_failed_and_the_later_steps_still_run(self):
        with self.failing_spec_for(self.members["today"]):
            summary = jobs.run_steps(only=list(DAILY))
        self.assertFalse(summary["ok"])
        renewal, owner = summary["steps"]
        self.assertFalse(renewal["ok"])
        self.assertEqual(renewal["processing_errors"], 1)
        self.assertTrue(owner["ok"])  # the owner summary still ran
        self.assertEqual(owner["created"], 1)

    def test_the_command_exits_non_zero_so_github_actions_shows_a_red_run(self):
        with self.failing_spec_for(self.members["today"]):
            with self.assertRaisesMessage(CommandError, "renewal_notifications"):
                call_command("run_scheduled_jobs", "--only", "renewal_notifications", stdout=io.StringIO())
        self.assertEqual(Notification.objects.count(), 2)  # the work that succeeded stays saved

    def test_the_next_run_completes_only_the_missing_work(self):
        with self.failing_spec_for(self.members["today"]):
            scheduled.renewal_notifications()
        retry = scheduled.renewal_notifications()
        self.assertEqual((retry["created"], retry["skipped"], retry["processing_errors"]), (1, 2, 0))
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(NotificationDelivery.objects.count(), 3)
        again = scheduled.renewal_notifications()
        self.assertEqual((again["created"], again["skipped"]), (0, 3))

    def test_a_failed_batch_insert_is_retried_one_by_one(self):
        real = services.notify_many

        def flaky(specs):
            if len(specs) > 1:
                raise RuntimeError("batch insert failed")
            return real(specs)

        # Put two members in the same milestone so a batch of two exists.
        extra = make_membership(library=self.library, plan=self.plan, student=make_student())
        Membership.objects.filter(pk=extra.pk).update(
            start_date=business_today() - timedelta(days=28), next_due_date=business_today() + timedelta(days=2)
        )
        with mock.patch.object(services, "notify_many", side_effect=flaky):
            summary = scheduled.renewal_notifications()
        self.assertEqual((summary["created"], summary["processing_errors"]), (4, 0))
        self.assertEqual(Notification.objects.count(), 4)

    def test_one_row_that_keeps_failing_is_counted_and_the_rest_are_saved(self):
        real = services.notify_many
        bad = str(self.members["late"].pk)

        def flaky(specs):
            if any(bad in spec.dedup_key for spec in specs):
                raise RuntimeError("this row cannot be saved")
            return real(specs)

        with mock.patch.object(services, "notify_many", side_effect=flaky):
            summary = scheduled.renewal_notifications()
        self.assertEqual((summary["created"], summary["processing_errors"]), (2, 1))
        self.assertFalse(Notification.objects.filter(recipient=self.members["late"].student).exists())

    def test_an_owner_summary_failure_does_not_stop_other_libraries(self):
        other, other_plan, other_seats = bookable_library()
        other_member = make_membership(library=other, plan=other_plan, seat=other_seats[0], student=make_student())
        Membership.objects.filter(pk=other_member.pk).update(
            start_date=business_today() - timedelta(days=30), next_due_date=business_today()
        )
        real = services.notify_many
        bad = str(self.library.pk)

        def flaky(specs):
            if any(bad in spec.dedup_key for spec in specs):
                raise RuntimeError("this summary cannot be saved")
            return real(specs)

        with mock.patch.object(services, "notify_many", side_effect=flaky):
            summary = scheduled.owner_summaries()
        self.assertEqual((summary["created"], summary["processing_errors"]), (1, 1))
        self.assertTrue(Notification.objects.filter(recipient=other.owner, type="owner_daily_dues_summary").exists())


class ProviderDisabledTests(JobBase):
    """No email provider is configured: reminders are in-app only and nothing claims to have been emailed."""

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_reminders_are_in_app_only_with_no_delivery_rows(self):
        summary = run_command(*DAILY, "send_emails")
        self.assertTrue(summary["ok"])
        self.assertEqual(Notification.objects.count(), 4)  # three reminders and one owner summary
        self.assertEqual(NotificationDelivery.objects.count(), 0)
        send = step_figures(summary, "send_emails")
        self.assertEqual((send["attempted"], send["sent"], send["failed"], send["disabled"]), (0, 0, 0, 1))
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_nothing_is_marked_sent_when_email_is_off(self):
        run_command(*DAILY, "send_emails")
        self.assertFalse(NotificationDelivery.objects.filter(status=NotificationDelivery.Status.SENT).exists())

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_the_in_app_inbox_still_works(self):
        run_command(*DAILY)
        student = client_for(self.members["soon"].student)
        items = student.get("/api/v1/notifications/").json()["data"]["items"]
        self.assertEqual([item["type"] for item in items], ["renewal_due_soon"])
        owner = client_for(self.library.owner)
        self.assertEqual(owner.get("/api/v1/notifications/unread-count/").json()["data"]["count"], 1)


class ChannelsEndpointTests(PaymentTestCase):
    """`GET /notifications/channels/` tells the owner screen whether email really goes out."""

    URL = "/api/v1/notifications/channels/"
    SMTP = "django.core.mail.backends.smtp.EmailBackend"
    CONSOLE = "django.core.mail.backends.console.EmailBackend"

    def channels(self, user=None):
        response = client_for(user or self.library.owner).get(self.URL)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False, EMAIL_BACKEND=SMTP)
    def test_email_is_off_when_the_switch_is_off(self):
        self.assertEqual(self.channels(), {"in_app": True, "email": False})

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True, EMAIL_BACKEND=CONSOLE)
    def test_email_is_off_with_a_backend_that_does_not_deliver(self):
        self.assertEqual(self.channels(), {"in_app": True, "email": False})

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_is_off_with_the_in_memory_backend(self):
        self.assertFalse(self.channels()["email"])

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=True, EMAIL_BACKEND=SMTP)
    def test_email_is_on_only_with_the_switch_and_a_real_backend(self):
        self.assertEqual(self.channels(), {"in_app": True, "email": True})

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_students_get_the_same_answer_and_anonymous_users_are_refused(self):
        self.assertEqual(self.channels(self.student), {"in_app": True, "email": False})
        self.assertEqual(APIClient().get(self.URL).status_code, 401)


class AutoCloseWorkflowTests(AttendanceBase):
    """The hourly workflow: stale records are closed at the library's closing time, in IST, safely repeated."""

    def setUp(self):
        super().setUp()
        type(self.library).objects.filter(pk=self.library.pk).update(closes_at=time(22, 0))

    def test_a_forgotten_check_out_is_closed_at_closing_time_not_at_run_time(self):
        with at_utc(2026, 11, 30, 4, 30):  # 10:00 IST on 30 Nov
            attendance.check_in(student=self.student, library_id=self.library.pk)
        with at_utc(2026, 12, 1, 3, 47):  # the next morning's run, 09:17 IST
            first = run_command("auto_close_attendance")
        self.assertTrue(first["ok"])
        self.assertEqual(step_figures(first, "auto_close_attendance")["closed"], 1)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.status, "auto_closed")
        self.assertEqual(record.check_out_at, datetime(2026, 11, 30, 16, 30, tzinfo=UTC))  # 22:00 IST

        with at_utc(2026, 12, 1, 4, 47):  # running it again closes nothing more
            second = run_command("auto_close_attendance")
        self.assertEqual(step_figures(second, "auto_close_attendance")["closed"], 0)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_a_student_can_check_in_again_once_the_stale_record_is_closed(self):
        with at_utc(2026, 11, 30, 4, 30):
            attendance.check_in(student=self.student, library_id=self.library.pk)
        with at_utc(2026, 12, 1, 3, 47):
            run_command("auto_close_attendance")
            record = attendance.check_in(student=self.student, library_id=self.library.pk)
        self.assertEqual(record.date, date(2026, 12, 1))
        self.assertEqual(AttendanceRecord.objects.count(), 2)

    def test_the_record_day_and_closing_time_use_the_ist_date_not_the_utc_date(self):
        with at_utc(2026, 11, 30, 18, 40):  # 00:10 IST on 1 Dec, still 30 Nov in UTC
            record = attendance.check_in(student=self.student, library_id=self.library.pk)
        self.assertEqual(record.date, date(2026, 12, 1))
        with at_utc(2026, 12, 1, 16, 0):  # 21:30 IST: the library is still open
            self.assertEqual(step_figures(run_command("auto_close_attendance"), "auto_close_attendance")["closed"], 0)
        with at_utc(2026, 12, 1, 17, 0):  # 22:30 IST: past closing time
            self.assertEqual(step_figures(run_command("auto_close_attendance"), "auto_close_attendance")["closed"], 1)

    def test_a_record_still_inside_opening_hours_is_left_open(self):
        with at_utc(2026, 12, 1, 4, 30):  # 10:00 IST
            attendance.check_in(student=self.student, library_id=self.library.pk)
            summary = run_command("auto_close_attendance")
        self.assertEqual(step_figures(summary, "auto_close_attendance")["closed"], 0)
        self.assertIsNone(AttendanceRecord.objects.get().check_out_at)
