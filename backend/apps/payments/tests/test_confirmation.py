"""Checkout verification (#42), webhook (#43), confirmation and reconciliation (SECURITY.md 10.5, SPEC.md 4.3)."""

import json
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import AppError
from apps.core.models import AuditLog
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments import gateway, services
from apps.payments.models import Payment, PaymentWebhookEvent
from apps.seats import selectors as seat_selectors
from apps.seats import services as seat_services
from apps.seats.models import Seat, SeatHold

from .base import (
    FakeGateway,
    PaymentTestCase,
    bookable_library,
    captured_event,
    client_for,
    failed_event,
)


class CheckoutVerificationTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.hold = self.hold_seat()
        self.order = self.order_for(self.hold)
        self.order_id = self.order["order_id"]

    def test_valid_signature_confirms_the_booking(self):
        response = self.verify(self.order_id, "pay_ok_1")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        payment = Payment.objects.get()
        today = timezone.localdate()
        self.assertEqual(data["payment"]["status"], "success")
        self.assertEqual(data["payment"]["receipt_number"], payment.receipt_number)
        self.assertEqual(data["payment"]["amount"], "1200.00")
        self.assertEqual(data["payment"]["period_start"], str(today))
        self.assertEqual(data["payment"]["period_end"], str(today + timedelta(days=30)))
        membership = Membership.objects.get()
        self.assertEqual(data["membership"]["id"], str(membership.pk))
        self.assertEqual(data["membership"]["seat"], {"id": str(self.seat.pk), "label": "A-1"})
        self.assertEqual(
            (data["membership"]["next_due_date"], data["membership"]["status"]),
            (str(today + timedelta(days=30)), "active"),
        )
        self.assertEqual(
            (payment.status, payment.verified_via, payment.gateway_payment_id), ("success", "checkout", "pay_ok_1")
        )
        self.assertEqual((payment.membership_id, payment.paid_at is not None), (membership.pk, True))
        self.assertEqual(
            (membership.student_id, membership.seat_id, membership.source, membership.state),
            (self.student.pk, self.seat.pk, "online", "active"),
        )
        self.hold.refresh_from_db()
        self.assertEqual(self.hold.status, "completed")
        self.assertEqual(seat_selectors.seat_counts_by_library([self.library.pk])[self.library.pk]["occupied"], 1)

    def test_confirmation_notifies_student_and_owner_once_and_audits(self):
        self.verify(self.order_id, "pay_ok_1")
        payment = Payment.objects.get()
        mine = Notification.objects.get(recipient=self.student)
        owners = Notification.objects.get(recipient=self.library.owner)
        self.assertEqual(
            (mine.type, mine.dedup_key),
            ("booking_confirmed", f"payment:{payment.pk}:booking_confirmed:{self.student.pk}"),
        )
        self.assertEqual(
            (owners.type, owners.dedup_key),
            ("payment_received", f"payment:{payment.pk}:payment_received:{self.library.owner.pk}"),
        )
        self.assertEqual(mine.entity_type, "membership")
        self.assertTrue(
            AuditLog.objects.filter(action="payment.status_change", entity_id=payment.pk, library=self.library).exists()
        )
        self.assertTrue(AuditLog.objects.filter(action="membership.create", library=self.library).exists())

    def test_repeating_verify_is_idempotent(self):
        first = self.verify(self.order_id, "pay_ok_1").json()["data"]
        for _ in range(3):
            again = self.verify(self.order_id, "pay_ok_1")
            self.assertEqual(again.status_code, 200)
            self.assertEqual(again.json()["data"], first)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(AuditLog.objects.filter(action="payment.status_change").count(), 1)

    def test_forged_signature_is_rejected_and_changes_nothing(self):
        with self.assertLogs("apps.security", level="WARNING") as logs:
            response = self.verify(self.order_id, "pay_ok_1", signature="0" * 64)
        self.assertEqual((response.status_code, self.error_code(response)), (400, "INVALID_SIGNATURE"))
        self.assertTrue(any("invalid_payment_signature" in line for line in logs.output))
        self.assert_untouched()

    def test_signature_made_with_the_wrong_secret_is_rejected(self):
        wrong = self.gateway.checkout_signature(self.order_id, "pay_ok_1", secret="some-other-secret")
        self.assertEqual(self.error_code(self.verify(self.order_id, "pay_ok_1", signature=wrong)), "INVALID_SIGNATURE")
        self.assert_untouched()

    def test_signature_for_a_different_payment_id_is_rejected(self):
        signature = self.gateway.checkout_signature(self.order_id, "pay_ok_1")
        self.assertEqual(
            self.error_code(self.verify(self.order_id, "pay_other", signature=signature)), "INVALID_SIGNATURE"
        )
        self.assert_untouched()

    def test_webhook_secret_cannot_sign_a_checkout(self):
        wrong = self.gateway.checkout_signature(self.order_id, "pay_ok_1", secret=settings.RAZORPAY_WEBHOOK_SECRET)
        self.assertEqual(self.error_code(self.verify(self.order_id, "pay_ok_1", signature=wrong)), "INVALID_SIGNATURE")

    @override_settings(RAZORPAY_KEY_SECRET="")
    def test_an_unconfigured_secret_never_verifies_anything(self):
        blank = FakeGateway()
        gateway.use_gateway(blank)
        self.assertEqual(blank.key_secret, "")
        forged = self.gateway.checkout_signature(self.order_id, "pay_ok_1", secret="")
        self.assertEqual(self.error_code(self.verify(self.order_id, "pay_ok_1", signature=forged)), "INVALID_SIGNATURE")
        self.assert_untouched()

    def test_another_students_order_is_404_even_with_a_valid_signature(self):
        response = self.verify(self.order_id, "pay_ok_1", student=make_student())
        self.assertEqual((response.status_code, self.error_code(response)), (404, "NOT_FOUND"))
        self.assert_untouched()

    def test_client_supplied_amount_is_ignored(self):
        response = self.verify(self.order_id, "pay_ok_1", amount="1.00", razorpay_amount=100)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["payment"]["amount"], "1200.00")
        self.assertEqual(str(Payment.objects.get().amount), "1200.00")

    def test_validation_and_roles(self):
        client = client_for(self.student)
        self.assertEqual(
            client.post("/api/v1/payments/verify/", {"razorpay_order_id": self.order_id}, format="json").status_code,
            400,
        )
        self.assertEqual(self.verify(self.order_id, "pay_ok_1", student=self.library.owner).status_code, 403)
        self.assertEqual(APIClient().post("/api/v1/payments/verify/", {}, format="json").status_code, 401)

    def test_unknown_order_is_404(self):
        self.assertEqual(self.verify("order_nope", "pay_ok_1").status_code, 404)

    def assert_untouched(self):
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.gateway_payment_id, payment.membership_id), ("pending", None, None))
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(Notification.objects.exists())
        self.hold.refresh_from_db()
        self.assertEqual(self.hold.status, "pending")


class WebhookTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.hold = self.hold_seat()
        self.order_id = self.order_for(self.hold)["order_id"]

    def test_a_valid_captured_webhook_confirms_without_the_browser(self):
        response = self.paid(self.order_id)
        self.assertEqual((response.status_code, response.json()["data"]), (200, {"status": "ok"}))
        payment = Payment.objects.get()
        self.assertEqual(
            (payment.status, payment.verified_via, payment.gateway_payment_id), ("success", "webhook", "pay_ok_1")
        )
        self.assertEqual(Membership.objects.count(), 1)
        event = PaymentWebhookEvent.objects.get()
        self.assertEqual(
            (event.event_type, event.result, event.processed_at is not None), ("payment.captured", "processed", True)
        )

    def test_order_paid_event_also_confirms(self):
        body = {
            "event": "order.paid",
            "payload": {
                "order": {"entity": {"id": self.order_id}},
                "payment": {"entity": {"id": "pay_ok_1", "order_id": self.order_id, "amount": 120000}},
            },
        }
        self.assertEqual(self.webhook(body).status_code, 200)
        self.assertEqual(Payment.objects.get().status, "success")

    def test_invalid_signature_is_400_logged_and_not_stored(self):
        body = captured_event(self.order_id, "pay_ok_1", 120000)
        with self.assertLogs("apps.security", level="WARNING") as logs:
            response = self.webhook(body, signature="f" * 64)
        self.assertEqual((response.status_code, self.error_code(response)), (400, "INVALID_SIGNATURE"))
        self.assertTrue(any("invalid_webhook_signature" in line for line in logs.output))
        self.assertFalse(PaymentWebhookEvent.objects.exists())
        self.assertEqual(Payment.objects.get().status, "pending")

    def test_signature_made_with_the_wrong_secret_or_the_key_secret_is_rejected(self):
        raw = b'{"event":"payment.captured"}'
        for secret in ("wrong", settings.RAZORPAY_KEY_SECRET):
            response = self.webhook(raw, signature=self.gateway.webhook_signature(raw, secret=secret))
            self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    def test_missing_signature_header_is_rejected(self):
        self.assertEqual(self.webhook(captured_event(self.order_id, "pay_ok_1"), headers=False).status_code, 400)
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    def test_the_signature_covers_the_raw_bytes_not_the_parsed_json(self):
        raw = b'{ "event" : "payment.captured" }'
        tampered = self.gateway.webhook_signature(b'{"event":"payment.captured"}')
        self.assertEqual(self.webhook(raw, signature=tampered).status_code, 400)

    def test_replaying_the_same_event_three_times_confirms_once(self):
        body = captured_event(self.order_id, "pay_ok_1", 120000)
        for _ in range(3):
            self.assertEqual(self.webhook(body, event_id="evt_same").status_code, 200)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)
        raw = json.dumps(body).encode()
        self.assertEqual(
            services.handle_webhook(raw_body=raw, signature=self.gateway.webhook_signature(raw), event_id="evt_same"),
            "ignored_duplicate",
        )

    def test_different_events_for_the_same_payment_confirm_once(self):
        for event in ("payment.captured", "order.paid"):
            body = captured_event(self.order_id, "pay_ok_1", 120000, event=event)
            self.assertEqual(self.webhook(body).status_code, 200)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 2)

    def test_checkout_after_webhook_and_webhook_after_checkout_are_both_harmless(self):
        self.paid(self.order_id)
        self.assertEqual(self.verify(self.order_id, "pay_ok_1").status_code, 200)
        self.assertEqual(self.paid(self.order_id).status_code, 200)
        self.assertEqual((Membership.objects.count(), Payment.objects.filter(status="success").count()), (1, 1))

    def test_payment_failed_marks_the_pending_payment_failed_and_leaves_the_hold(self):
        self.assertEqual(self.webhook(failed_event(self.order_id, "pay_bad", "Card declined")).status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.failure_reason), ("failed", "Card declined"))
        self.hold.refresh_from_db()
        self.assertEqual(self.hold.status, "pending")
        self.assertFalse(Membership.objects.exists())

    def test_a_late_failed_event_never_overwrites_a_success(self):
        self.paid(self.order_id)
        self.webhook(failed_event(self.order_id, "pay_ok_1"))
        self.assertEqual(Payment.objects.get().status, "success")

    def test_money_wins_over_an_earlier_failure(self):
        self.webhook(failed_event(self.order_id, "pay_bad"))
        self.assertEqual(Payment.objects.get().status, "failed")
        self.paid(self.order_id, "pay_retry_ok")
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.gateway_payment_id), ("success", "pay_retry_ok"))
        self.assertEqual(Membership.objects.count(), 1)

    def test_money_wins_over_a_client_side_cancel(self):
        Payment.objects.filter(pk=Payment.objects.get().pk).update(status="cancelled")
        self.assertEqual(self.verify(self.order_id, "pay_ok_1").status_code, 200)
        self.assertEqual(Payment.objects.get().status, "success")

    def test_unknown_event_types_and_unknown_orders_are_ignored_with_a_200(self):
        self.assertEqual(self.webhook({"event": "refund.created", "payload": {}}).status_code, 200)
        self.assertEqual(self.paid("order_nobody_knows").status_code, 200)
        self.assertEqual(
            list(PaymentWebhookEvent.objects.order_by("received_at").values_list("result", flat=True)),
            ["ignored_unknown", "ignored_unknown"],
        )
        self.assertEqual(Payment.objects.get().status, "pending")

    def test_amount_mismatch_never_confirms_and_still_answers_200(self):
        response = self.paid(self.order_id, amount_paise=100)
        self.assertEqual(response.status_code, 200)
        event = PaymentWebhookEvent.objects.get()
        self.assertEqual(event.result, "error")
        self.assertIn("does not match", event.error)
        self.assertEqual(Payment.objects.get().status, "pending")
        self.assertFalse(Membership.objects.exists())

    def test_processing_errors_are_recorded_and_answered_200(self):
        other = Payment.objects.get()
        Payment.objects.filter(pk=other.pk).update(gateway_payment_id="pay_taken")
        # a second order that tries to reuse a gateway payment id already bound to another payment
        hold2 = self.hold_seat(student=make_student(), seat=self.seats[1])
        order2 = self.order_for(hold2)["order_id"]
        response = self.paid(order2, payment_id="pay_taken")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PaymentWebhookEvent.objects.get().result, "error")
        self.assertEqual(Payment.objects.get(gateway_order_id=order2).status, "pending")

    def test_bad_requests_after_a_valid_signature(self):
        self.assertEqual(self.webhook(b"not json at all").status_code, 400)
        raw = b'{"event":"payment.captured"}'
        self.assertEqual(self.webhook(raw, event_id="").status_code, 400)
        self.assertEqual(self.webhook(raw, event_id="e" * 65).status_code, 400)

    def test_the_endpoint_is_csrf_exempt_and_needs_no_login(self):
        response = self.webhook(captured_event(self.order_id, "pay_ok_1", 120000), enforce_csrf=True)
        self.assertEqual(response.status_code, 200)


class LateCaptureTests(PaymentTestCase):
    """Money arrives after the hold died: confirm if the seat is free, `needs_refund` if not, never two members."""

    def setUp(self):
        super().setUp()
        self.hold = self.hold_seat()
        self.order_id = self.order_for(self.hold)["order_id"]

    def test_hold_expired_but_seat_still_free_is_re_acquired_and_confirmed(self):
        self.expire(self.hold)
        self.assertEqual(self.paid(self.order_id).status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual(payment.status, "success")
        self.hold.refresh_from_db()
        self.assertEqual(self.hold.status, "completed")
        self.assertEqual(Membership.objects.get().seat_id, self.seat.pk)

    def test_hold_cleaned_up_and_released_by_the_owner_is_still_re_acquired_if_free(self):
        SeatHold.objects.filter(pk=self.hold.pk).update(status="released", closed_at=timezone.now())
        self.paid(self.order_id)
        self.assertEqual(Payment.objects.get().status, "success")

    def test_seat_taken_by_another_member_means_needs_refund_and_one_occupant(self):
        self.expire(self.hold)
        seat_services.expire_dead_holds()
        other = make_student()
        make_membership(library=self.library, plan=self.plan, seat=self.seat, student=other)
        self.assertEqual(self.paid(self.order_id).status_code, 200)
        payment = Payment.objects.get()
        self.assertEqual(
            (payment.status, payment.verified_via, payment.membership_id), ("needs_refund", "webhook", None)
        )
        self.assertEqual(payment.gateway_payment_id, "pay_ok_1")
        self.assertIn("no longer available", payment.failure_reason)
        self.assertEqual(Membership.objects.filter(seat=self.seat, state="active").count(), 1)
        self.assertEqual(Membership.objects.get(seat=self.seat).student_id, other.pk)
        types = {(n.recipient_id, n.type) for n in Notification.objects.all()}
        self.assertEqual(
            types, {(self.student.pk, "payment_needs_refund"), (self.library.owner.pk, "payment_needs_refund")}
        )

    def test_seat_taken_by_another_students_live_hold_means_needs_refund(self):
        self.expire(self.hold)
        self.hold_seat(student=make_student())  # a new live hold now owns the seat
        self.paid(self.order_id)
        self.assertEqual(Payment.objects.get(gateway_order_id=self.order_id).status, "needs_refund")
        self.assertFalse(Membership.objects.exists())

    def test_checkout_verify_reports_seat_lost_and_stays_refund_pending(self):
        self.expire(self.hold)
        make_membership(library=self.library, plan=self.plan, seat=self.seat, student=make_student())
        response = self.verify(self.order_id, "pay_ok_1")
        self.assertEqual((response.status_code, self.error_code(response)), (409, "SEAT_LOST_REFUND_PENDING"))
        self.assertEqual(Payment.objects.get().status, "needs_refund")
        again = self.verify(self.order_id, "pay_ok_1")
        self.assertEqual(self.error_code(again), "SEAT_LOST_REFUND_PENDING")
        self.assertEqual(Notification.objects.filter(type="payment_needs_refund").count(), 2)  # not repeated

    def test_a_student_who_became_a_member_elsewhere_in_the_library_needs_a_refund(self):
        self.expire(self.hold)
        make_membership(library=self.library, plan=self.plan, seat=self.seats[2], student=self.student)
        self.paid(self.order_id)
        self.assertEqual(Payment.objects.get().status, "needs_refund")
        self.assertEqual(Membership.objects.filter(student=self.student, state="active").count(), 1)

    def test_a_disabled_or_removed_seat_means_needs_refund(self):
        self.expire(self.hold)
        Seat.objects.filter(pk=self.seat.pk).update(is_disabled=True, disabled_reason="Broken")
        self.paid(self.order_id)
        self.assertEqual(Payment.objects.get().status, "needs_refund")

    def test_needs_refund_is_final(self):
        self.expire(self.hold)
        make_membership(library=self.library, plan=self.plan, seat=self.seat, student=make_student())
        self.paid(self.order_id)
        self.paid(self.order_id, "pay_ok_2")
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.gateway_payment_id), ("needs_refund", "pay_ok_1"))


class ReconcileTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.hold = self.hold_seat()
        self.order_id = self.order_for(self.hold)["order_id"]
        self.payment = Payment.objects.get()

    def age(self, minutes=45):
        Payment.objects.filter(pk=self.payment.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))

    def test_a_captured_stale_order_is_confirmed_via_reconcile(self):
        self.age()
        self.gateway.capture(self.order_id, "pay_ok_1", 120000)
        counts = services.reconcile_stale_orders()
        self.assertEqual((counts["checked"], counts["confirmed"]), (1, 1))
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.verified_via), ("success", "reconcile"))
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(services.reconcile_stale_orders()["checked"], 0)  # idempotent

    def test_no_capture_and_a_dead_hold_cancels_the_payment(self):
        self.age()
        self.expire(self.hold)
        counts = services.reconcile_stale_orders()
        self.assertEqual(counts["cancelled"], 1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "cancelled")

    def test_no_capture_with_a_live_hold_stays_pending(self):
        self.age()
        counts = services.reconcile_stale_orders()
        self.assertEqual((counts["confirmed"], counts["cancelled"]), (0, 0))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_recent_orders_are_left_alone(self):
        self.gateway.capture(self.order_id, "pay_ok_1", 120000)
        self.assertEqual(services.reconcile_stale_orders()["checked"], 0)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")

    def test_a_gateway_outage_is_counted_and_does_not_raise(self):
        self.age()
        self.gateway.fail_lookups = True
        counts = services.reconcile_stale_orders()
        self.assertEqual((counts["errors"], counts["confirmed"]), (1, 0))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "pending")


class ConcurrentConfirmationTests(TransactionTestCase):
    """Verify and webhook racing for one payment: exactly one membership, one set of notifications."""

    def setUp(self):
        self.gateway = FakeGateway()
        gateway.use_gateway(self.gateway)
        self.addCleanup(gateway.use_gateway, None)
        self.library, self.plan, self.seats = bookable_library(domain_codes=[], amenity_codes=[])

    def race(self, jobs):
        barrier = threading.Barrier(len(jobs))
        outcomes: list[str] = []

        def worker(job):
            try:
                barrier.wait(timeout=15)
                outcomes.append(str(job()))
            except AppError as exc:
                outcomes.append(exc.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(job,)) for job in jobs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return outcomes

    def test_verify_and_webhook_race_confirms_exactly_once(self):
        student = make_student()
        hold = seat_services.create_booking_hold(student=student, seat_id=self.seats[0].pk, plan_id=self.plan.pk)
        order_id = services.create_order(student=student, hold_id=hold.pk).order_id
        sig = self.gateway.checkout_signature(order_id, "pay_race")
        raw = json.dumps(captured_event(order_id, "pay_race", 120000)).encode()

        jobs = [
            lambda: (
                services.verify_checkout(
                    student=student, order_id=order_id, payment_id="pay_race", signature=sig
                ).payment.status
            ),
            lambda: services.handle_webhook(
                raw_body=raw, signature=self.gateway.webhook_signature(raw), event_id="evt_race_1"
            ),
            lambda: (
                services.verify_checkout(
                    student=student, order_id=order_id, payment_id="pay_race", signature=sig
                ).payment.status
            ),
            lambda: services.confirm_payment(order_id=order_id, gateway_payment_id="pay_race", via="reconcile").status,
        ]
        outcomes = self.race(jobs)
        self.assertEqual(len(outcomes), 4, outcomes)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Payment.objects.get().status, "success")
        self.assertEqual(Notification.objects.filter(type="booking_confirmed").count(), 1)
        self.assertEqual(Notification.objects.filter(type="payment_received").count(), 1)

    def test_two_payments_for_one_seat_never_make_two_members(self):
        """A late capture and a fresh booking racing for one seat: the seat lock and the uniques give one winner."""
        first, second = make_student(), make_student()
        hold1 = seat_services.create_booking_hold(student=first, seat_id=self.seats[0].pk, plan_id=self.plan.pk)
        order1 = services.create_order(student=first, hold_id=hold1.pk).order_id
        SeatHold.objects.filter(pk=hold1.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        hold2 = seat_services.create_booking_hold(student=second, seat_id=self.seats[0].pk, plan_id=self.plan.pk)
        order2 = services.create_order(student=second, hold_id=hold2.pk).order_id

        jobs = [
            lambda: services.confirm_payment(order_id=order1, gateway_payment_id="pay_a", via="webhook").status,
            lambda: services.confirm_payment(order_id=order2, gateway_payment_id="pay_b", via="webhook").status,
        ]
        outcomes = self.race(jobs)
        self.assertEqual(sorted(outcomes), ["needs_refund", "success"])
        self.assertEqual(Membership.objects.filter(seat=self.seats[0], state="active").count(), 1)
        self.assertEqual(Payment.objects.filter(status="success").count(), 1)
        self.assertEqual(Payment.objects.filter(status="needs_refund").count(), 1)
