"""Payment history #44-#45, owner ledger #46-#47, ledger integrity and the gateway adapter."""

import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import GatewayError
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.tests.base import make_plan
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments import gateway
from apps.payments.gateway import RazorpayGateway
from apps.payments.models import Payment, next_receipt_number
from apps.seats import services as seat_services
from apps.seats.models import SeatHold

from .base import PaymentTestCase, bookable_library, client_for


class LedgerTestCase(PaymentTestCase):
    def pay(self, student=None, seat=None, payment_id=None):
        """Run a full booking: hold, order, verified payment. Returns the Payment."""
        student = student or self.student
        hold = self.hold_seat(student=student, seat=seat)
        order_id = self.order_for(hold)["order_id"]
        response = self.verify(order_id, payment_id or f"pay_{order_id}", student=student)
        assert response.status_code == 200, response.content
        return Payment.objects.get(gateway_order_id=order_id)

    def pending(self, student, seat):
        hold = self.hold_seat(student=student, seat=seat)
        self.order_for(hold)
        return Payment.objects.get(hold=hold)


class StudentHistoryTests(LedgerTestCase):
    def test_lists_only_my_payments_newest_first_with_the_documented_fields(self):
        mine = self.pay()
        self.pay(student=make_student(), seat=self.seats[1])
        data = client_for(self.student).get("/api/v1/student/payments/").json()["data"]
        self.assertEqual([p["id"] for p in data["items"]], [str(mine.pk)])
        item = data["items"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "library",
                "purpose",
                "method",
                "amount",
                "status",
                "receipt_number",
                "period_start",
                "period_end",
                "paid_at",
                "created_at",
            },
        )
        self.assertEqual(
            (item["amount"], item["status"], item["purpose"], item["method"]),
            ("1200.00", "success", "new_membership", "gateway"),
        )
        self.assertEqual(item["library"], {"id": str(self.library.pk), "name": self.library.name})
        for hidden in ("gateway_order_id", "gateway_payment_id", "verified_via", "recorded_by"):
            self.assertNotIn(hidden, item)

    def test_order_id_filter_is_an_exact_match_for_checkout(self):
        payment = self.pending(self.student, self.seats[0])
        data = (
            client_for(self.student)
            .get("/api/v1/student/payments/", {"order_id": payment.gateway_order_id})
            .json()["data"]
        )
        self.assertEqual([p["status"] for p in data["items"]], ["pending"])
        none = client_for(self.student).get("/api/v1/student/payments/", {"order_id": "order_nope"}).json()["data"]
        self.assertEqual(none["items"], [])
        other = (
            client_for(make_student())
            .get("/api/v1/student/payments/", {"order_id": payment.gateway_order_id})
            .json()["data"]
        )
        self.assertEqual(other["items"], [])

    def test_receipt_view_has_contact_plan_and_seat(self):
        payment = self.pay()
        data = client_for(self.student).get(f"/api/v1/student/payments/{payment.pk}/").json()["data"]
        self.assertEqual(data["receipt_number"], payment.receipt_number)
        self.assertEqual((data["plan_name"], data["seat_label"]), (self.plan.name, "A-1"))
        self.assertEqual(set(data["library_contact"]), {"phone", "email", "address"})
        self.assertEqual(data["library_contact"]["address"], self.library.address)

    def test_someone_elses_receipt_is_404(self):
        payment = self.pay()
        for client in (client_for(make_student()), client_for(self.library.owner)):
            self.assertIn(client.get(f"/api/v1/student/payments/{payment.pk}/").status_code, (403, 404))
        self.assertEqual(client_for(make_student()).get(f"/api/v1/student/payments/{payment.pk}/").status_code, 404)

    def test_login_and_role_required(self):
        self.assertEqual(APIClient().get("/api/v1/student/payments/").status_code, 401)
        self.assertEqual(client_for(self.library.owner).get("/api/v1/student/payments/").status_code, 403)

    def test_pagination(self):
        for _ in range(3):
            hold = self.hold_seat(student=self.student, seat=self.seats[0])
            self.order_for(hold)
            SeatHold.objects.filter(pk=hold.pk).update(status="cancelled")
        data = client_for(self.student).get("/api/v1/student/payments/", {"page_size": 2}).json()["data"]
        self.assertEqual((len(data["items"]), data["total"], data["page"]), (2, 3, 1))


class OwnerLedgerTests(LedgerTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)

    def test_owner_sees_only_their_librarys_payments_with_student_details(self):
        paid = self.pay()
        _other_library, other_plan, other_seats = bookable_library(name="Other Library")
        other_student = make_student()
        other_hold = seat_services.create_booking_hold(
            student=other_student, seat_id=other_seats[0].pk, plan_id=other_plan.pk
        )
        self.order_for(other_hold)
        data = self.owner.get("/api/v1/owner/payments/").json()["data"]
        self.assertEqual([p["id"] for p in data["items"]], [str(paid.pk)])
        item = data["items"][0]
        self.assertEqual(
            item["student"], {"id": str(self.student.pk), "name": self.student.name, "phone": self.student.phone}
        )
        self.assertEqual((item["channel"], item["recorded_by"]), ("online", None))

    def test_filters(self):
        paid = self.pay()
        pending = self.pending(make_student(name="Ravi Kumar", phone="+919811111111"), self.seats[1])
        client = self.owner
        ids = lambda **q: {p["id"] for p in client.get("/api/v1/owner/payments/", q).json()["data"]["items"]}  # noqa: E731
        self.assertEqual(ids(status="success"), {str(paid.pk)})
        self.assertEqual(ids(status="pending"), {str(pending.pk)})
        self.assertEqual(ids(method="gateway"), {str(paid.pk), str(pending.pk)})
        self.assertEqual(ids(method="cash"), set())
        self.assertEqual(ids(channel="online"), {str(paid.pk), str(pending.pk)})
        self.assertEqual(ids(search="ravi"), {str(pending.pk)})
        self.assertEqual(ids(search="9811111111"), {str(pending.pk)})
        today = timezone.localdate()
        self.assertEqual(ids(date_from=str(today), date_to=str(today)), {str(paid.pk), str(pending.pk)})
        self.assertEqual(ids(date_from=str(today + timedelta(days=1))), set())
        self.assertEqual(ids(date_to=str(today - timedelta(days=1))), set())

    def test_bad_filters_are_400(self):
        for query in ({"status": "bogus"}, {"method": "barter"}, {"date_from": "yesterday"}):
            self.assertEqual(self.owner.get("/api/v1/owner/payments/", query).status_code, 400)

    def test_detail_and_isolation(self):
        paid = self.pay()
        data = self.owner.get(f"/api/v1/owner/payments/{paid.pk}/").json()["data"]
        self.assertEqual((data["plan_name"], data["seat_label"], data["failure_reason"]), (self.plan.name, "A-1", ""))
        for hidden in ("gateway_order_id", "gateway_payment_id", "verified_via"):
            self.assertNotIn(hidden, data)
        other_owner = client_for(bookable_library(name="Other Library")[0].owner)
        self.assertEqual(other_owner.get(f"/api/v1/owner/payments/{paid.pk}/").status_code, 404)
        self.assertEqual(other_owner.get("/api/v1/owner/payments/").json()["data"]["items"], [])

    def test_roles(self):
        self.assertEqual(APIClient().get("/api/v1/owner/payments/").status_code, 401)
        self.assertEqual(client_for(self.student).get("/api/v1/owner/payments/").status_code, 403)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/payments/").status_code, 409)


class LedgerIntegrityTests(LedgerTestCase):
    def values(self, **overrides):
        base = {
            "library": self.library,
            "student": self.student,
            "plan": self.plan,
            "purpose": "new_membership",
            "channel": "online",
            "method": "gateway",
            "amount": Decimal("1200.00"),
            "gateway_order_id": f"order_{timezone.now().timestamp()}",
            "receipt_number": next_receipt_number(2026),
        }
        return {**base, **overrides}

    def assert_rejected(self, **overrides):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(**self.values(**overrides))

    def test_database_constraints(self):
        membership = make_membership(library=self.library, plan=self.plan, seat=self.seats[0], student=self.student)
        self.assert_rejected(amount=Decimal("0"))
        self.assert_rejected(amount=Decimal("-5"))
        self.assert_rejected(gateway_order_id=None)  # online needs an order
        self.assert_rejected(
            channel="offline", method="cash", gateway_order_id=None
        )  # offline needs recorded_by + success
        self.assert_rejected(
            channel="offline", method="cash", gateway_order_id=None, recorded_by=self.library.owner
        )  # not success
        self.assert_rejected(status="success")  # success needs paid_at, period and membership
        self.assert_rejected(
            status="success", paid_at=timezone.now(), period_start=timezone.localdate(), period_end=timezone.localdate()
        )
        self.assert_rejected(purpose="renewal")  # renewal needs a membership
        self.assert_rejected(status="refunded")
        self.assert_rejected(method="barter")
        Payment.objects.create(
            **self.values(
                channel="offline",
                method="cash",
                gateway_order_id=None,
                recorded_by=self.library.owner,
                status="success",
                paid_at=timezone.now(),
                membership=membership,
                period_start=membership.start_date,
                period_end=membership.next_due_date,
            )
        )

    def test_unique_order_payment_and_receipt(self):
        first = Payment.objects.create(
            **self.values(gateway_order_id="order_unique_1", gateway_payment_id="pay_unique_1")
        )
        self.assert_rejected(gateway_order_id="order_unique_1")
        self.assert_rejected(gateway_order_id="order_unique_2", gateway_payment_id="pay_unique_1")
        self.assert_rejected(gateway_order_id="order_unique_3", receipt_number=first.receipt_number)

    def test_receipt_sequence_is_unique_and_increasing(self):
        numbers = [next_receipt_number(2026) for _ in range(5)]
        self.assertEqual(numbers, sorted(set(numbers)))
        self.assertTrue(all(n.startswith("LH-2026-") and len(n.split("-")[2]) == 6 for n in numbers))

    def test_core_fields_are_immutable_once_created(self):
        created = Payment.objects.create(**self.values())
        other_plan = make_plan(self.library, name="Quarterly", duration_days=90, price=Decimal("3000.00"))
        other_library = bookable_library(name="Other Library")[0]
        changes = {
            "amount": Decimal("1.00"),
            "plan": other_plan,
            "student": make_student(),
            "library": other_library,
            "channel": "offline",
            "purpose": "renewal",
        }
        for field, value in changes.items():
            fresh = Payment.objects.get(pk=created.pk)
            setattr(fresh, field, value)
            with self.assertRaises(TypeError, msg=field):
                fresh.save()
        self.assertEqual(str(Payment.objects.get(pk=created.pk).amount), "1200.00")

    def test_mutable_fields_can_still_change(self):
        created = Payment.objects.create(**self.values())
        fresh = Payment.objects.get(pk=created.pk)
        fresh.notes = "checked by hand"
        fresh.save()
        self.assertEqual(Payment.objects.get(pk=created.pk).notes, "checked by hand")

    def test_payments_cannot_be_deleted(self):
        payment = Payment.objects.create(**self.values())
        with self.assertRaises(TypeError):
            payment.delete()

    def test_status_transitions_follow_the_state_machine(self):
        payment = Payment.objects.create(**self.values())
        payment.move_to("failed")
        payment.move_to("success")  # money that arrives always wins
        for blocked in ("pending", "failed", "cancelled", "needs_refund"):
            with self.assertRaises(ValueError):
                payment.move_to(blocked)
        refund = Payment.objects.create(**self.values())
        refund.move_to("needs_refund")
        with self.assertRaises(ValueError):
            refund.move_to("success")
        cancelled = Payment.objects.create(**self.values())
        cancelled.move_to("cancelled")
        cancelled.move_to("needs_refund")


class GatewayAdapterTests(SimpleTestCase):
    SECRET = "unit-test-key-secret"

    def test_checkout_signature_matches_the_documented_algorithm(self):
        expected = hmac.new(self.SECRET.encode(), b"order_1|pay_1", hashlib.sha256).hexdigest()
        client = RazorpayGateway()
        self.assertTrue(client.verify_checkout_signature(order_id="order_1", payment_id="pay_1", signature=expected))
        self.assertFalse(client.verify_checkout_signature(order_id="order_1", payment_id="pay_2", signature=expected))
        self.assertFalse(client.verify_checkout_signature(order_id="order_2", payment_id="pay_1", signature=expected))
        self.assertFalse(
            client.verify_checkout_signature(order_id="order_1", payment_id="pay_1", signature=expected.upper())
        )

    def test_webhook_signature_is_over_the_raw_bytes(self):
        raw = b'{"event": "payment.captured"}'
        good = hmac.new(b"unit-test-webhook-secret", raw, hashlib.sha256).hexdigest()
        client = RazorpayGateway()
        self.assertTrue(client.verify_webhook_signature(raw_body=raw, signature=good))
        self.assertFalse(client.verify_webhook_signature(raw_body=raw + b" ", signature=good))
        self.assertFalse(client.verify_webhook_signature(raw_body=raw, signature=""))

    @override_settings(RAZORPAY_KEY_SECRET="", RAZORPAY_WEBHOOK_SECRET="")
    def test_empty_secrets_never_verify_even_an_empty_or_precomputed_signature(self):
        client = RazorpayGateway()
        empty_key = hmac.new(b"", b"o|p", hashlib.sha256).hexdigest()
        empty_hook = hmac.new(b"", b"{}", hashlib.sha256).hexdigest()
        self.assertFalse(client.verify_checkout_signature(order_id="o", payment_id="p", signature=empty_key))
        self.assertFalse(client.verify_webhook_signature(raw_body=b"{}", signature=empty_hook))
        self.assertFalse(client.verify_webhook_signature(raw_body=b"{}", signature=""))

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_unconfigured_gateway_fails_safely_with_a_502(self):
        client = RazorpayGateway()
        with self.assertRaises(GatewayError):
            client.create_order(amount_paise=100, receipt="r", notes={})
        with self.assertRaises(GatewayError):
            client.fetch_order_payments(order_id="order_1")

    def test_orders_and_lookups_map_sdk_results_and_wrap_sdk_failures(self):
        calls = {}

        class Orders:
            def create(self, data):
                calls["create"] = data
                return {"id": "order_9", "amount": data["amount"], "currency": "INR"}

            def payments(self, order_id):
                return {"items": [{"id": "pay_9", "status": "captured", "amount": 120000}]}

        client = RazorpayGateway()
        client._client = SimpleNamespace(order=Orders())
        order = client.create_order(amount_paise=120000, receipt="LH-2026-000001", notes={"hold_id": "h"})
        self.assertEqual((order.order_id, order.amount_paise, order.currency), ("order_9", 120000, "INR"))
        self.assertEqual(
            calls["create"],
            {"amount": 120000, "currency": "INR", "receipt": "LH-2026-000001", "notes": {"hold_id": "h"}},
        )
        payments = client.fetch_order_payments(order_id="order_9")
        self.assertEqual([(p.payment_id, p.status, p.amount_paise) for p in payments], [("pay_9", "captured", 120000)])

        class Broken:
            def create(self, data):
                raise ConnectionError("network down")

            def payments(self, order_id):
                raise ConnectionError("network down")

        client._client = SimpleNamespace(order=Broken())
        with self.assertRaises(GatewayError):
            client.create_order(amount_paise=1, receipt="r", notes={})
        with self.assertRaises(GatewayError):
            client.fetch_order_payments(order_id="order_9")

    def test_the_sdk_is_imported_only_by_the_gateway_module(self):
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[2]
        offenders = [
            str(path.relative_to(root))
            for path in root.rglob("*.py")
            if "razorpay" in path.read_text(encoding="utf-8").replace("RAZORPAY", "")
            and "import razorpay" in path.read_text(encoding="utf-8")
            and path.name != "gateway.py"
            and "tests" not in path.parts
        ]
        self.assertEqual(offenders, [])

    def test_default_gateway_is_razorpay_unless_a_test_override_is_installed(self):
        gateway.use_gateway(None)
        self.assertIsInstance(gateway.get_gateway(), RazorpayGateway)
