"""Email delivery state machine and retry rules (NOT-07, NOT-08)."""

import threading
from datetime import UTC, datetime, timedelta

from django.core import mail
from django.db import connection
from django.test import TestCase, TransactionTestCase

from apps.core.tests.factories import make_student
from apps.notifications import selectors, services
from apps.notifications.models import NotificationDelivery
from apps.notifications.senders import DjangoEmailSender, backoff_after, send_delivery

T0 = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class FakeSender:
    def __init__(self, *failures):
        self.failures = list(failures)
        self.sent = []

    def send(self, *, to, subject, body):
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append((to, subject, body))
        return f"<msg-{len(self.sent)}@test>"


class DeliveryTests(TestCase):
    def setUp(self):
        self.student = make_student(name="Asha Rao")
        note = services.notify(
            recipient=self.student,
            type="payment_received",
            title="Payment received",
            body="₹1,200 paid.",
            dedup_key="k",
        )
        self.delivery = note.deliveries.get()

    def refresh(self):
        self.delivery.refresh_from_db()
        return self.delivery

    def test_success_marks_sent_and_records_the_provider_id(self):
        sender = FakeSender()
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0), "sent")
        delivery = self.refresh()
        self.assertEqual((delivery.status, delivery.attempts, delivery.sent_at), ("sent", 1, T0))
        self.assertEqual(delivery.provider_message_id, "<msg-1@test>")
        to, subject, body = sender.sent[0]
        self.assertEqual((to, subject), (self.student.email, "Payment received"))
        self.assertIn("Hi Asha Rao", body)
        self.assertIn("₹1,200 paid.", body)

    def test_a_sent_delivery_is_never_sent_again(self):
        sender = FakeSender()
        send_delivery(self.delivery.pk, sender=sender, now=T0)
        for _ in range(3):
            self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0 + timedelta(days=1)), "sent")
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(self.refresh().attempts, 1)

    def test_failure_is_recorded_and_retried_with_backoff(self):
        sender = FakeSender(ConnectionError("smtp down"))
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0), "failed")
        delivery = self.refresh()
        self.assertEqual((delivery.attempts, delivery.last_error), (1, "ConnectionError: smtp down"))
        self.assertEqual(delivery.next_attempt_at, T0 + timedelta(minutes=15))
        # not due yet: nothing happens, nothing is counted
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0 + timedelta(minutes=14)), "failed")
        self.assertEqual(self.refresh().attempts, 1)
        # due: the retry succeeds without duplicating anything
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0 + timedelta(minutes=15)), "sent")
        delivery = self.refresh()
        self.assertEqual((delivery.attempts, delivery.last_error, delivery.next_attempt_at), (2, "", None))
        self.assertEqual(len(sender.sent), 1)

    def test_backoff_doubles_and_stops_after_five_attempts(self):
        self.assertEqual([backoff_after(n) for n in (1, 2, 3, 4)], [timedelta(minutes=m) for m in (15, 30, 60, 120)])
        sender = FakeSender(*[RuntimeError("boom")] * 6)
        now = T0
        gaps = []
        for _ in range(5):
            send_delivery(self.delivery.pk, sender=sender, now=now)
            delivery = self.refresh()
            if delivery.next_attempt_at is None:
                break
            gaps.append(delivery.next_attempt_at - now)
            now = delivery.next_attempt_at
        self.assertEqual(gaps, [timedelta(minutes=m) for m in (15, 30, 60, 120)])
        delivery = self.refresh()
        self.assertEqual((delivery.status, delivery.attempts, delivery.next_attempt_at), ("failed", 5, None))
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=now + timedelta(days=30)), "failed")
        self.assertEqual(self.refresh().attempts, 5)  # gave up for good
        self.assertEqual(len(sender.failures), 1)  # the sixth failure was never consumed

    def test_long_provider_errors_fit_the_column(self):
        send_delivery(self.delivery.pk, sender=FakeSender(RuntimeError("x" * 2000)), now=T0)
        self.assertEqual(len(self.refresh().last_error), 500)

    def test_recipient_who_lost_their_email_is_skipped(self):
        type(self.student).objects.filter(pk=self.student.pk).update(email=None, is_offline=True)
        sender = FakeSender()
        self.assertEqual(send_delivery(self.delivery.pk, sender=sender, now=T0), "skipped")
        self.assertEqual(sender.sent, [])

    def test_unknown_delivery_returns_none(self):
        import uuid

        self.assertIsNone(send_delivery(uuid.uuid4(), sender=FakeSender(), now=T0))

    def test_default_sender_uses_the_django_email_backend(self):
        self.assertEqual(send_delivery(self.delivery.pk, now=T0), "sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.student.email])
        self.assertTrue(self.refresh().provider_message_id.startswith("<"))
        self.assertTrue(DjangoEmailSender().send(to="a@b.in", subject="s", body="b"))


class DueDeliveryTests(TestCase):
    def test_selector_returns_only_attemptable_rows(self):
        students = [make_student() for _ in range(5)]
        rows = [
            services.notify(
                recipient=s, type="account_claimed", title="t", body="b", dedup_key=f"k{i}"
            ).deliveries.get()
            for i, s in enumerate(students)
        ]
        pending, retry_due, retry_later, gave_up, sent = rows
        NotificationDelivery.objects.filter(pk=retry_due.pk).update(
            status="failed", attempts=2, next_attempt_at=T0 - timedelta(minutes=1)
        )
        NotificationDelivery.objects.filter(pk=retry_later.pk).update(
            status="failed", attempts=1, next_attempt_at=T0 + timedelta(minutes=10)
        )
        NotificationDelivery.objects.filter(pk=gave_up.pk).update(status="failed", attempts=5, next_attempt_at=None)
        NotificationDelivery.objects.filter(pk=sent.pk).update(status="sent", attempts=1)
        due = set(selectors.due_deliveries(now=T0).values_list("pk", flat=True))
        self.assertEqual(due, {pending.pk, retry_due.pk})


class OverlappingRunTests(TransactionTestCase):
    """Two job runs reaching the same delivery at once: one sends, the other skips the locked row."""

    def test_second_run_does_not_send_while_the_first_holds_the_row(self):
        student = make_student()
        delivery = services.notify(
            recipient=student, type="account_claimed", title="t", body="b", dedup_key="k"
        ).deliveries.get()
        in_send, release = threading.Event(), threading.Event()
        sent: list[str] = []

        class SlowSender:
            def send(self, *, to, subject, body):
                sent.append(to)
                in_send.set()
                release.wait(timeout=10)
                return "<slow@test>"

        outcome: dict[str, object] = {}

        def first():
            try:
                outcome["first"] = send_delivery(delivery.pk, sender=SlowSender(), now=T0)
            finally:
                connection.close()

        def second():
            try:
                in_send.wait(timeout=10)
                outcome["second"] = send_delivery(delivery.pk, sender=SlowSender(), now=T0)
            finally:
                release.set()
                connection.close()

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(outcome, {"first": "sent", "second": None})
        self.assertEqual(len(sent), 1)
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.attempts), ("sent", 1))
