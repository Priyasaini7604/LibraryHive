"""Creating orders (#41, new booking): server-side amount, one pending order per hold, safe failures."""

import re
from itertools import pairwise

from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.factories import make_student
from apps.payments.models import Payment
from apps.seats.models import SeatHold

from .base import PaymentTestCase, client_for

ORDERS = "/api/v1/payments/orders/"


class CreateOrderTests(PaymentTestCase):
    def test_creates_a_pending_payment_and_the_documented_response(self):
        hold = self.hold_seat()
        response = client_for(self.student).post(ORDERS, {"hold_id": str(hold.pk)}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(
            set(data),
            {"payment_id", "gateway", "key_id", "order_id", "amount_paise", "currency", "description", "prefill"},
        )
        self.assertEqual((data["gateway"], data["currency"], data["amount_paise"]), ("razorpay", "INR", 120000))
        self.assertEqual(data["key_id"], "rzp_test_unit_tests")
        self.assertEqual(
            data["prefill"], {"name": self.student.name, "email": self.student.email, "phone": self.student.phone}
        )
        self.assertIn(self.plan.name, data["description"])
        payment = Payment.objects.get(pk=data["payment_id"])
        self.assertEqual(
            (payment.status, payment.channel, payment.method, payment.purpose, str(payment.amount), payment.currency),
            ("pending", "online", "gateway", "new_membership", "1200.00", "INR"),
        )
        self.assertEqual(
            (payment.student_id, payment.library_id, payment.plan_id, payment.hold_id),
            (self.student.pk, self.library.pk, self.plan.pk, hold.pk),
        )
        self.assertEqual(payment.gateway_order_id, data["order_id"])
        self.assertIsNone(payment.membership_id)

    def test_amount_comes_from_the_plan_and_the_client_cannot_change_it(self):
        hold = self.hold_seat()
        response = client_for(self.student).post(
            ORDERS, {"hold_id": str(hold.pk), "amount": "1.00", "amount_paise": 100, "plan_id": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["amount_paise"], 120000)
        self.assertEqual(self.gateway.orders[0]["order"].amount_paise, 120000)
        self.assertEqual(str(Payment.objects.get().amount), "1200.00")

    def test_paise_are_exact_for_fractional_prices(self):
        type(self.plan).objects.filter(pk=self.plan.pk).update(price="999.99")
        data = self.order_for(self.hold_seat())
        self.assertEqual(data["amount_paise"], 99999)

    def test_receipt_number_format_and_gateway_receipt(self):
        hold = self.hold_seat()
        self.order_for(hold)
        payment = Payment.objects.get()
        self.assertTrue(
            re.fullmatch(rf"LH-{timezone.localdate().year}-\d{{6}}", payment.receipt_number), payment.receipt_number
        )
        self.assertEqual(self.gateway.orders[0]["receipt"], payment.receipt_number)
        self.assertEqual(self.gateway.orders[0]["notes"]["hold_id"], str(hold.pk))

    def test_receipt_numbers_increase_and_never_repeat(self):
        numbers = []
        for _ in range(3):
            student = make_student()
            hold = self.hold_seat(student=student)
            self.order_for(hold)
            numbers.append(Payment.objects.get(hold=hold).receipt_number)
            SeatHold.objects.filter(pk=hold.pk).update(status="cancelled")
        self.assertEqual(numbers, sorted(set(numbers)))
        sequence = [int(n.rsplit("-", 1)[1]) for n in numbers]
        self.assertTrue(all(b > a for a, b in pairwise(sequence)))

    def test_a_second_order_for_the_same_hold_cancels_the_older_pending_one(self):
        hold = self.hold_seat()
        first = self.order_for(hold)
        second = self.order_for(hold)
        self.assertNotEqual(first["order_id"], second["order_id"])
        statuses = dict(Payment.objects.filter(hold=hold).values_list("gateway_order_id", "status"))
        self.assertEqual(statuses, {first["order_id"]: "cancelled", second["order_id"]: "pending"})

    def test_another_students_hold_is_404_and_creates_nothing(self):
        hold = self.hold_seat()
        response = client_for(make_student()).post(ORDERS, {"hold_id": str(hold.pk)}, format="json")
        self.assertEqual((response.status_code, self.error_code(response)), (404, "NOT_FOUND"))
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.gateway.orders, [])

    def test_manual_holds_cannot_be_paid_for(self):
        manual = SeatHold.objects.create(
            seat=self.seats[1],
            library=self.library,
            kind="owner_manual",
            reason="Reserved",
            created_by=self.library.owner,
        )
        response = client_for(self.student).post(ORDERS, {"hold_id": str(manual.pk)}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_expired_or_closed_hold_is_hold_expired(self):
        hold = self.hold_seat()
        self.expire(hold)
        response = client_for(self.student).post(ORDERS, {"hold_id": str(hold.pk)}, format="json")
        self.assertEqual((response.status_code, self.error_code(response)), (409, "HOLD_EXPIRED"))
        cancelled = self.hold_seat(seat=self.seats[1])
        SeatHold.objects.filter(pk=cancelled.pk).update(status="cancelled")
        self.assertEqual(
            self.error_code(client_for(self.student).post(ORDERS, {"hold_id": str(cancelled.pk)}, format="json")),
            "HOLD_EXPIRED",
        )
        self.assertFalse(Payment.objects.exists())

    def test_inactive_plan_is_plan_inactive(self):
        hold = self.hold_seat()
        type(self.plan).objects.filter(pk=self.plan.pk).update(is_active=False)
        response = client_for(self.student).post(ORDERS, {"hold_id": str(hold.pk)}, format="json")
        self.assertEqual((response.status_code, self.error_code(response)), (409, "PLAN_INACTIVE"))

    def test_gateway_failure_is_a_502_and_leaves_nothing_behind(self):
        hold = self.hold_seat()
        self.gateway.fail_orders = True
        response = client_for(self.student).post(ORDERS, {"hold_id": str(hold.pk)}, format="json")
        self.assertEqual((response.status_code, self.error_code(response)), (502, "GATEWAY_ERROR"))
        self.assertFalse(Payment.objects.exists())
        hold.refresh_from_db()
        self.assertEqual(hold.status, "pending")  # the student can retry while the hold lives
        self.gateway.fail_orders = False
        self.assertEqual(
            client_for(self.student).post(ORDERS, {"hold_id": str(hold.pk)}, format="json").status_code, 201
        )

    def test_validation_and_roles(self):
        client = client_for(self.student)
        for payload in ({}, {"hold_id": "not-a-uuid"}):
            self.assertEqual(client.post(ORDERS, payload, format="json").status_code, 400)
        hold = self.hold_seat()
        self.assertEqual(APIClient().post(ORDERS, {"hold_id": str(hold.pk)}, format="json").status_code, 401)
        owner = client_for(self.library.owner)
        self.assertEqual(owner.post(ORDERS, {"hold_id": str(hold.pk)}, format="json").status_code, 403)


class CancelHoldCancelsPendingPaymentTests(PaymentTestCase):
    """#40: abandoning a booking hold also closes the hold's pending Payment."""

    def cancel(self, hold, student=None):
        return client_for(student or self.student).post(f"/api/v1/student/holds/{hold.pk}/cancel/", format="json")

    def test_cancelling_the_hold_cancels_its_pending_payment(self):
        hold = self.hold_seat()
        self.order_for(hold)
        self.assertEqual(self.cancel(hold).status_code, 200)
        self.assertEqual(Payment.objects.get(hold=hold).status, "cancelled")

    def test_cancelling_without_an_order_still_works(self):
        hold = self.hold_seat()
        self.assertEqual(self.cancel(hold).status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_another_students_cancel_leaves_the_payment_pending(self):
        hold = self.hold_seat()
        self.order_for(hold)
        self.assertEqual(self.cancel(hold, make_student()).status_code, 404)
        self.assertEqual(Payment.objects.get(hold=hold).status, "pending")

    def test_money_arriving_after_the_cancel_still_wins_and_never_double_books(self):
        hold = self.hold_seat()
        order = self.order_for(hold)
        self.cancel(hold)
        self.assertEqual(self.paid(order["order_id"]).status_code, 200)
        payment = Payment.objects.get(hold=hold)
        self.assertIn(payment.status, {"success", "needs_refund"})
