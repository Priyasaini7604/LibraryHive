"""notify(): deduplication (NOT-06), delivery rows (NOT-07), input safety."""

import threading
import uuid

from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from apps.core.tests.factories import make_owner, make_student
from apps.notifications import services
from apps.notifications.models import Notification, NotificationDelivery
from apps.notifications.services import NotificationSpec


def spec(recipient, key="renewal:m1:due_soon:2026-10-20:r1", **overrides):
    values = {
        "recipient": recipient,
        "type": Notification.Type.RENEWAL_DUE_SOON,
        "title": "Your seat is due in 3 days",
        "body": "Renew by 20 Oct to keep your seat.",
        "dedup_key": key,
        **overrides,
    }
    return NotificationSpec(**values)


class DedupTests(TestCase):
    def setUp(self):
        self.student = make_student()

    def test_first_call_creates_and_replays_do_not(self):
        first = services.notify(
            recipient=self.student, type="renewal_due_soon", title="Due soon", body="b", dedup_key="k1"
        )
        self.assertIsNotNone(first)
        for _ in range(4):
            again = services.notify(
                recipient=self.student, type="renewal_due_soon", title="Due soon", body="b", dedup_key="k1"
            )
            self.assertIsNone(again)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)  # one email queued, not five

    def test_the_same_event_five_times_in_one_batch_creates_one_row(self):
        created = services.notify_many([spec(self.student) for _ in range(5)])
        self.assertEqual(len(created), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_batch_skips_existing_keys_and_returns_only_new_ones(self):
        services.notify_many([spec(self.student, key="a")])
        created = services.notify_many([spec(self.student, key="a"), spec(self.student, key="b")])
        self.assertEqual([n.dedup_key for n in created], ["b"])
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(NotificationDelivery.objects.count(), 2)

    def test_different_recipients_with_different_keys_both_get_one(self):
        other = make_student()
        services.notify_many([spec(self.student, key="x:1"), spec(other, key="x:2")])
        self.assertEqual(Notification.objects.filter(recipient=self.student).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=other).count(), 1)

    def test_a_key_collision_keeps_the_original_row_untouched(self):
        services.notify(recipient=self.student, type="renewal_due_soon", title="Original", body="b", dedup_key="k")
        services.notify(recipient=make_student(), type="payment_received", title="Impostor", body="x", dedup_key="k")
        row = Notification.objects.get(dedup_key="k")
        self.assertEqual((row.title, row.recipient_id), ("Original", self.student.pk))

    def test_database_enforces_the_unique_key(self):
        services.notify(recipient=self.student, type="renewal_due_soon", title="t", body="b", dedup_key="k")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(
                recipient=self.student, type="renewal_due_soon", title="t", body="b", dedup_key="k"
            )

    def test_empty_batch_is_a_no_op(self):
        self.assertEqual(services.notify_many([]), [])


class ContentTests(TestCase):
    def setUp(self):
        self.student = make_student()

    def test_entity_deep_link_is_stored(self):
        entity_id = uuid.uuid4()
        note = services.notify(
            recipient=self.student,
            type="booking_confirmed",
            title="Booked",
            body="Seat A-3 is yours.",
            dedup_key="payment:p1:booking_confirmed:r",
            entity=("membership", entity_id),
        )
        note.refresh_from_db()
        self.assertEqual((note.entity_type, note.entity_id), ("membership", entity_id))

    def test_entity_is_optional(self):
        note = services.notify(recipient=self.student, type="account_claimed", title="t", body="b", dedup_key="k")
        self.assertEqual((note.entity_type, note.entity_id), (None, None))

    def test_oversize_text_is_shortened_instead_of_failing_the_caller(self):
        note = services.notify(
            recipient=self.student, type="complaint_updated", title="T" * 400, body="B" * 5000, dedup_key="k"
        )
        note.refresh_from_db()
        self.assertEqual((len(note.title), len(note.body)), (150, 1000))
        self.assertTrue(note.title.endswith("…") and note.body.endswith("…"))

    def test_unknown_type_and_bad_keys_are_programming_errors(self):
        for kwargs in (
            {"type": "made_up", "dedup_key": "k"},
            {"type": "account_claimed", "dedup_key": ""},
            {"type": "account_claimed", "dedup_key": "k" * 201},
        ):
            with self.assertRaises(ValueError):
                services.notify(recipient=self.student, title="t", body="b", **kwargs)
        self.assertFalse(Notification.objects.exists())

    def test_every_documented_type_is_accepted(self):
        for index, value in enumerate(Notification.Type.values):
            self.assertIsNotNone(
                services.notify(recipient=self.student, type=value, title="t", body="b", dedup_key=f"k{index}")
            )

    def test_notification_joins_the_callers_transaction(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            services.notify(recipient=self.student, type="account_claimed", title="t", body="b", dedup_key="k")
            raise RuntimeError("business step failed")
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(NotificationDelivery.objects.exists())


class DeliveryRowTests(TestCase):
    def test_recipient_with_email_gets_a_pending_email_delivery(self):
        student = make_student()
        note = services.notify(recipient=student, type="account_claimed", title="t", body="b", dedup_key="k")
        delivery = note.deliveries.get()
        self.assertEqual((delivery.channel, delivery.status, delivery.attempts), ("email", "pending", 0))
        self.assertEqual(mail.outbox, [])  # notify() queues; sending is the scheduled job's work

    def test_recipient_without_email_gets_a_skipped_row(self):
        offline = make_student()
        type(offline).objects.filter(pk=offline.pk).update(email=None, is_offline=True)
        offline.refresh_from_db()
        note = services.notify(recipient=offline, type="booking_confirmed", title="t", body="b", dedup_key="k")
        self.assertEqual(note.deliveries.get().status, "skipped")

    @override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
    def test_email_switched_off_keeps_in_app_only(self):
        note = services.notify(recipient=make_owner(), type="visit_requested", title="t", body="b", dedup_key="k")
        self.assertIsNotNone(note)
        self.assertFalse(NotificationDelivery.objects.exists())

    def test_database_allows_one_email_delivery_per_notification_and_caps_attempts(self):
        note = services.notify(recipient=make_student(), type="account_claimed", title="t", body="b", dedup_key="k")
        with self.assertRaises(IntegrityError), transaction.atomic():
            NotificationDelivery.objects.create(notification=note, channel="email")
        with self.assertRaises(IntegrityError), transaction.atomic():
            NotificationDelivery.objects.filter(notification=note).update(attempts=6)


class ConcurrentDedupTests(TransactionTestCase):
    """Eight workers inserting the same event: exactly one notification and one delivery survive."""

    def test_parallel_notify_with_one_key_creates_one_row(self):
        student = make_student()
        barrier = threading.Barrier(8)
        created: list[bool] = []

        def worker():
            try:
                barrier.wait(timeout=10)
                note = services.notify(
                    recipient=student, type="payment_received", title="t", body="b", dedup_key="payment:p:x:r"
                )
                created.append(note is not None)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(sorted(created), [False] * 7 + [True])
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)
