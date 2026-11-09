"""Pilot-readiness rules for direct UPI payments: one approval message, gateway availability, the review-time
policy, safe resubmission, and how analytics keeps manual UPI apart from the online gateway."""

from datetime import timedelta

from django.utils import timezone

from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments import gateway, services
from apps.payments.models import Payment, UpiPaymentRequest
from apps.seats import services as seat_services
from apps.seats.models import SeatHold

from .base import bookable_library, client_for
from .test_upi import BASE, UpiTestCase


class ApprovalNotificationTests(UpiTestCase):
    """One approval, one message to the student (the offline-payment helper stays quiet for UPI)."""

    def test_the_student_gets_exactly_one_notification_for_an_approval(self):
        self.enable_upi()
        request = self.submitted()
        self.approve(request)
        mine = Notification.objects.filter(recipient=self.student)
        self.assertEqual(list(mine.values_list("type", flat=True)), ["upi_payment_approved"])

    def test_a_renewal_approval_is_also_a_single_message(self):
        self.enable_upi()
        membership = make_membership(
            library=self.library, plan=self.plan, student=self.student, seat=self.seat, due_in=3
        )
        response = self.student_api.post(
            f"{BASE}/student/upi-payments/",
            {"membership_id": str(membership.pk), "utr": self.next_utr()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.approve(UpiPaymentRequest.objects.get())
        self.assertEqual(Notification.objects.filter(recipient=self.student).count(), 1)

    def test_the_existing_offline_payment_still_tells_the_student(self):
        membership = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)
        services.record_offline_payment(
            membership=membership,
            plan=self.plan,
            purpose="renewal",
            method="cash",
            recorded_by=self.owner,
            period_start=membership.start_date,
            period_end=membership.next_due_date,
        )
        self.assertTrue(Notification.objects.filter(recipient=self.student, type="payment_received").exists())


class GatewayAvailabilityTests(UpiTestCase):
    """Screens hide the gateway button when no gateway keys exist; a configured gateway is unchanged."""

    def library_payload(self):
        return self.student_api.get(f"{BASE}/student/holds/current/").json()["data"][0]["library"]

    def test_gateway_is_reported_enabled_when_configured(self):
        self.hold_seat()
        self.assertTrue(self.library_payload()["gateway_enabled"])

    def test_gateway_is_reported_disabled_without_keys(self):
        self.hold_seat()
        gateway.use_gateway(None)  # the real adapter, as in production
        with self.settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET=""):
            self.assertFalse(self.library_payload()["gateway_enabled"])
        with self.settings(RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET="secret"):
            self.assertTrue(self.library_payload()["gateway_enabled"])

    def test_a_key_id_without_a_secret_does_not_count_as_configured(self):
        gateway.use_gateway(None)
        with self.settings(RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET=""):
            self.assertFalse(gateway.is_configured())

    def test_the_membership_payload_carries_the_same_flag(self):
        membership = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)
        gateway.use_gateway(None)
        with self.settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET=""):
            data = self.student_api.get(f"{BASE}/student/memberships/{membership.pk}/").json()["data"]
        self.assertFalse(data["library"]["gateway_enabled"])

    def test_a_configured_gateway_still_creates_orders_and_confirms_them(self):
        hold = self.hold_seat()
        order = self.order_for(hold)
        self.assertEqual(self.paid(order["order_id"]).status_code, 200)
        self.assertEqual(Membership.objects.get().student, self.student)


class ReviewTimePolicyTests(UpiTestCase):
    """A request waiting past the review target is flagged to both sides; nothing is decided automatically."""

    def setUp(self):
        super().setUp()
        self.enable_upi()

    def age(self, request, hours):
        UpiPaymentRequest.objects.filter(pk=request.pk).update(created_at=timezone.now() - timedelta(hours=hours))

    def student_view(self, request):
        return self.student_api.get(f"{BASE}/student/upi-payments/{request.pk}/").json()["data"]

    def test_a_fresh_request_is_not_overdue(self):
        data = self.student_view(self.submitted())
        self.assertEqual((data["waiting_hours"], data["overdue"]), (0, False))

    def test_an_old_pending_request_is_overdue_for_both_sides_but_stays_pending(self):
        request = self.submitted()
        self.age(request, 30)
        owner_view = self.owner_api.get(f"{BASE}/owner/upi-payments/{request.pk}/").json()["data"]
        for view in (self.student_view(request), owner_view):
            self.assertTrue(view["overdue"])
            self.assertEqual(view["waiting_hours"], 30)
            self.assertEqual(view["status"], "pending")  # never auto-approved, auto-rejected or "refunded"
        self.assertEqual(UpiPaymentRequest.objects.get().status, "pending")
        self.assertFalse(Payment.objects.exists())

    def test_the_target_is_configurable(self):
        request = self.submitted()
        self.age(request, 3)
        with self.settings(UPI_REVIEW_TARGET_HOURS=2):
            self.assertTrue(self.student_view(request)["overdue"])
        with self.settings(UPI_REVIEW_TARGET_HOURS=48):
            self.assertFalse(self.student_view(request)["overdue"])

    def test_the_owner_summary_counts_pending_and_overdue(self):
        old = self.submitted()
        self.age(old, 26)
        self.submitted(student=make_student())
        summary = f"{BASE}/owner/upi-payments/summary/"
        self.assertEqual(self.owner_api.get(summary).json()["data"], {"pending": 2, "overdue": 1})
        self.approve(old)
        self.assertEqual(self.owner_api.get(summary).json()["data"], {"pending": 1, "overdue": 0})

    def test_decided_requests_have_no_waiting_time(self):
        request = self.submitted()
        self.reject(request)
        data = self.student_view(request)
        self.assertEqual((data["waiting_hours"], data["overdue"]), (None, False))

    def test_an_overdue_request_can_still_be_approved_if_the_seat_is_free(self):
        request = self.submitted()
        self.age(request, 24 * 5)
        self.expire(request.hold)
        self.assertEqual(self.approve(request).status_code, 200)

    def test_the_summary_is_private_to_the_owners_library(self):
        self.submitted()
        other_library, _, _ = bookable_library(owner=make_owner(), domain_codes=[], amenity_codes=[])
        mine = client_for(other_library.owner).get(f"{BASE}/owner/upi-payments/summary/").json()["data"]
        self.assertEqual(mine, {"pending": 0, "overdue": 0})
        self.assertEqual(self.student_api.get(f"{BASE}/owner/upi-payments/summary/").status_code, 403)


class ResubmissionSafetyTests(UpiTestCase):
    """Cancelling and resubmitting: the same student may retry, nobody else may claim their reference."""

    def setUp(self):
        super().setUp()
        self.enable_upi()

    def test_the_same_student_can_resend_a_rejected_utr(self):
        first = self.submitted(utr="RETRY0000001")
        self.reject(first, "I could not find it, please check again")
        seat_services.cancel_hold(student=self.student, hold=first.hold)
        again = self.submit(utr="RETRY0000001")
        self.assertEqual(again.status_code, 201, again.content)
        self.assertEqual(UpiPaymentRequest.objects.filter(utr="RETRY0000001").count(), 2)

    def test_the_same_student_can_resend_after_cancelling(self):
        first = self.submitted(utr="RETRY0000002")
        self.student_api.post(f"{BASE}/student/upi-payments/{first.pk}/cancel/", {}, format="json")
        seat_services.cancel_hold(student=self.student, hold=first.hold)
        self.assertEqual(self.submit(utr="RETRY0000002").status_code, 201)

    def test_nobody_else_can_claim_a_rejected_or_cancelled_utr(self):
        first = self.submitted(utr="STOLEN000001")
        self.reject(first)
        thief = make_student()
        response = self.submit(student=thief, utr="STOLEN000001")
        self.assertEqual((response.status_code, self.error_code(response)), (409, "DUPLICATE_UTR"))
        SeatHold.objects.filter(student=thief).update(status="cancelled")

        second_student = make_student()
        second = self.submitted(student=second_student, utr="STOLEN000002")
        client_for(second_student).post(f"{BASE}/student/upi-payments/{second.pk}/cancel/", {}, format="json")
        SeatHold.objects.filter(student=second_student).update(status="cancelled")
        response = self.submit(student=thief, utr="STOLEN000002")
        self.assertEqual(self.error_code(response), "DUPLICATE_UTR")

    def test_an_approved_utr_is_never_reusable(self):
        first = self.submitted(utr="DONE00000001")
        self.approve(first)
        response = self.submit(student=make_student(), utr="DONE00000001")
        self.assertEqual(self.error_code(response), "DUPLICATE_UTR")

    def test_only_a_pending_request_can_be_cancelled(self):
        first = self.submitted(utr="CANCEL000009")
        self.approve(first)
        response = self.student_api.post(f"{BASE}/student/upi-payments/{first.pk}/cancel/", {}, format="json")
        self.assertEqual(self.error_code(response), "ALREADY_DECIDED")
        self.assertEqual(Membership.objects.count(), 1)  # cancelling after approval cannot undo the membership


class AnalyticsDistinguishesUpiTests(UpiTestCase):
    """Owner revenue and the dashboard keep manually verified UPI apart from the online gateway and count only
    approved money."""

    def revenue(self):
        today = timezone.localdate()
        response = self.owner_api.get(
            f"{BASE}/owner/reports/revenue/", {"from": str(today - timedelta(days=1)), "to": str(today)}
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]

    def test_pending_rejected_and_cancelled_requests_are_not_revenue(self):
        self.enable_upi()
        self.submitted()
        rejected = self.submitted(student=make_student())
        self.reject(rejected)
        cancelled_student = make_student()
        cancelled = self.submitted(student=cancelled_student)
        client_for(cancelled_student).post(f"{BASE}/student/upi-payments/{cancelled.pk}/cancel/", {}, format="json")
        self.assertEqual(self.revenue()["count"], 0)

    def test_an_approved_upi_payment_is_upi_direct_and_a_gateway_payment_stays_gateway(self):
        self.enable_upi()
        self.approve(self.submitted())

        other = make_student()
        hold = self.hold_seat(student=other, seat=self.seats[1])
        order = self.order_for(hold, student=other)
        self.paid(order["order_id"])

        data = self.revenue()
        self.assertEqual(set(data["by_method"]), {"upi_direct", "gateway"})
        self.assertEqual(data["by_method"]["upi_direct"], {"total": "1200.00", "count": 1})
        self.assertEqual(data["by_method"]["gateway"], {"total": "1200.00", "count": 1})
        self.assertEqual(data["total"], "2400.00")
        dashboard = self.owner_api.get(f"{BASE}/owner/dashboard/").json()["data"]
        self.assertEqual(set(dashboard["revenue"]["by_method"]), {"upi_direct", "gateway"})

    def test_the_owner_ledger_marks_upi_as_offline_and_gateway_as_online(self):
        self.enable_upi()
        self.approve(self.submitted())
        rows = self.owner_api.get(f"{BASE}/owner/payments/").json()["data"]["items"]
        self.assertEqual([(row["method"], row["channel"]) for row in rows], [("upi_direct", "offline")])
