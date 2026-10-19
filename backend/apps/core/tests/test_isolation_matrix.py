"""Cross-app tenant isolation matrix (SECURITY.md 6.2 G1, 6.3 G2, 6.4, section 20 "Isolation").

Two libraries, each with an owner and students, are filled with real rows through the real services and API:
a membership and payment (booked through the fake gateway), a live hold, an attendance record, a complaint, a
visit request and notifications. Then every row of the two attack tables is replayed:

- G1: Owner A against Library B's ids must get 404 and change nothing;
- G2: Student A against Student B's ids must get 404 and change nothing;
- "no B rows in any A list, report or export".

The e2e journey and each app's own tests cover the happy paths; this file only attacks.
"""

import json
import uuid
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.attendance.models import AttendanceRecord
from apps.complaints.models import Complaint
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for
from apps.seats import services as seat_services
from apps.seats.models import Seat, SeatHold
from apps.visits.models import VisitRequest

API = "/api/v1/"


def rows(response):
    data = response.json()["data"]
    return data["items"] if isinstance(data, dict) and "items" in data else data


class IsolationWorld(PaymentTestCase):
    """Library A is the base class's library; Library B is built here. Student B is a paying member of B."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.lib_a, self.seat_a = self.library, self.seats[0]
        self.owner_a = client_for(self.lib_a.owner)
        self.student_a = self.student
        self.me_a = client_for(self.student_a)
        self.member_a = self._join_a()

        self.lib_b, self.plan_b, self.seats_b = bookable_library()
        self.owner_b_user = self.lib_b.owner
        self.owner_b = client_for(self.owner_b_user)
        self.student_b = make_student(name="Bhavna Bee", email="bhavna.bee@example.com")
        self.me_b = client_for(self.student_b)

        # Student B books and pays through the real order and verify endpoints (fake gateway, nothing real).
        hold = seat_services.create_booking_hold(
            student=self.student_b, seat_id=self.seats_b[0].pk, plan_id=self.plan_b.pk
        )
        order = self.order_for(hold, student=self.student_b)
        response = self.verify(order["order_id"], "pay_b_1", student=self.student_b)
        assert response.status_code == 200, response.content
        self.member_b = Membership.objects.get(student=self.student_b)
        self.payment_b = Payment.objects.get(membership=self.member_b)
        self.seat_b = self.seats_b[0]

        # Student B's attendance, complaint and visit.
        assert (
            self.me_b.post(
                API + "student/attendance/check-in/", {"library_id": str(self.lib_b.pk)}, format="json"
            ).status_code
            == 201
        )
        self.record_b = AttendanceRecord.objects.get(student=self.student_b)
        assert (
            self.me_b.post(
                API + "student/complaints/",
                {
                    "library_id": str(self.lib_b.pk),
                    "category": "ac",
                    "description": "The cooling is not working at all.",
                },
                format="json",
            ).status_code
            == 201
        )
        self.complaint_b = Complaint.objects.get(student=self.student_b)
        visitor_b = make_student(name="Vikram Vee", email="vikram.vee@example.com")
        self.visitor_b = visitor_b
        assert (
            client_for(visitor_b)
            .post(
                API + "student/visits/",
                {
                    "library_id": str(self.lib_b.pk),
                    "preferred_date": str(timezone.localdate() + timedelta(days=3)),
                    "preferred_slot": "morning",
                    "student_note": "Looking around",
                },
                format="json",
            )
            .status_code
            == 201
        )
        self.visit_b = VisitRequest.objects.get(student=visitor_b)

        # A live hold and an unpaid order that belong to a third student at Library B.
        self.holder_b = make_student(name="Hari Hold", email="hari.hold@example.com")
        self.hold_b = seat_services.create_booking_hold(
            student=self.holder_b, seat_id=self.seats_b[1].pk, plan_id=self.plan_b.pk
        )
        self.order_b = self.order_for(self.hold_b, student=self.holder_b)
        self.notification_b = Notification.objects.filter(recipient=self.student_b).first()
        assert self.notification_b is not None

    def _join_a(self):
        from apps.memberships.tests.test_membership_model import make_membership

        return make_membership(library=self.lib_a, plan=self.plan, student=self.student_a, seat=self.seat_a)

    # helpers --------------------------------------------------------------------------------------------------
    def assert_404(self, response, what):
        self.assertEqual(
            response.status_code, 404, f"{what}: expected 404, got {response.status_code} {response.content[:200]}"
        )
        self.assertEqual(response.json()["error_code"], "NOT_FOUND", what)

    def assert_no_b_rows(self, text, what):
        forbidden = [
            str(self.member_b.pk),
            str(self.payment_b.pk),
            str(self.record_b.pk),
            str(self.complaint_b.pk),
            str(self.visit_b.pk),
            str(self.hold_b.pk),
            str(self.seat_b.pk),
            str(self.lib_b.pk),
            self.payment_b.receipt_number,
            "Bhavna Bee",
            "bhavna.bee@example.com",
            "Vikram Vee",
            "vikram.vee@example.com",
            "Hari Hold",
            "hari.hold@example.com",
            self.student_b.phone,
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text, f"{what} leaks {needle!r}")


class OwnerAgainstOtherLibraryTests(IsolationWorld):
    """SECURITY.md 6.2: Owner A against Library B's ids."""

    def test_member_endpoints_are_404_and_change_nothing(self):
        base = f"owner/members/{self.member_b.pk}/"
        self.assert_404(self.owner_a.get(API + base), "member detail")
        self.assert_404(
            self.owner_a.post(API + base + "renewals/", {"method": "cash"}, format="json"), "record renewal"
        )
        self.assert_404(
            self.owner_a.post(API + base + "archive/", {"reason": "No longer coming"}, format="json"), "archive"
        )
        self.member_b.refresh_from_db()
        self.assertEqual(self.member_b.state, Membership.State.ACTIVE)
        self.assertEqual(Payment.objects.filter(membership=self.member_b).count(), 1)

    def test_payment_complaint_visit_and_attendance_endpoints_are_404(self):
        self.assert_404(self.owner_a.get(API + f"owner/payments/{self.payment_b.pk}/"), "payment detail")
        self.assert_404(self.owner_a.get(API + f"owner/complaints/{self.complaint_b.pk}/"), "complaint detail")
        self.assert_404(
            self.owner_a.patch(
                API + f"owner/complaints/{self.complaint_b.pk}/",
                {"status": "resolved", "owner_response": "Done"},
                format="json",
            ),
            "complaint reply",
        )
        self.assert_404(
            self.owner_a.post(API + f"owner/visits/{self.visit_b.pk}/decision/", {"decision": "accept"}, format="json"),
            "visit decision",
        )
        self.assert_404(
            self.owner_a.post(
                API + "owner/attendance/check-in/", {"membership_id": str(self.member_b.pk)}, format="json"
            ),
            "manual check-in",
        )
        self.assert_404(self.owner_a.post(API + f"owner/attendance/{self.record_b.pk}/check-out/"), "manual check-out")
        self.assert_404(
            self.owner_a.patch(
                API + f"owner/attendance/{self.record_b.pk}/",
                {"check_out_at": timezone.now().isoformat(), "reason": "Not yours to edit"},
                format="json",
            ),
            "attendance correction",
        )
        self.complaint_b.refresh_from_db()
        self.visit_b.refresh_from_db()
        self.record_b.refresh_from_db()
        self.assertEqual(self.complaint_b.status, "open")
        self.assertEqual(self.visit_b.status, "pending")
        self.assertIsNone(self.record_b.check_out_at)

    def test_seat_and_hold_endpoints_are_404(self):
        seat_url = f"owner/seats/{self.seats_b[2].pk}/"
        self.assert_404(self.owner_a.patch(API + seat_url, {"label": "HACK"}, format="json"), "seat rename")
        for action in ("deactivate", "disable", "enable"):
            self.assert_404(
                self.owner_a.post(API + seat_url + action + "/", {"reason": "Not yours"}, format="json"), action
            )
        self.assert_404(
            self.owner_a.post(API + seat_url + "manual-hold/", {"reason": "Not yours"}, format="json"), "manual hold"
        )
        self.assert_404(
            self.owner_a.post(API + f"owner/holds/{self.hold_b.pk}/release/", {"reason": "Not yours"}, format="json"),
            "release hold",
        )
        self.assertFalse(SeatHold.objects.filter(seat=self.seats_b[2]).exists())
        self.hold_b.refresh_from_db()
        self.assertEqual(self.hold_b.status, SeatHold.Status.PENDING)
        label = Seat.objects.get(pk=self.seats_b[2].pk)
        self.assertNotEqual(label.label, "HACK")
        self.assertTrue(label.is_active and not label.is_disabled)

    def test_admission_with_ids_from_library_b_is_404_and_creates_nothing(self):
        def admit(**ids):
            return self.owner_a.post(
                API + "owner/admissions/",
                {
                    "student": {"name": "Walk In", "phone": "+919876500123", "email": ""},
                    "seat_id": str(self.seats[1].pk),
                    "plan_id": str(self.plan.pk),
                    "payment": {"method": "cash"},
                    **ids,
                },
                format="json",
            )

        before = Membership.objects.count()
        self.assert_404(admit(seat_id=str(self.seat_b.pk)), "admission with B's seat")
        self.assert_404(admit(plan_id=str(self.plan_b.pk)), "admission with B's plan")
        self.assertEqual(Membership.objects.count(), before)

    def test_claim_code_for_a_student_who_belongs_only_to_library_b_is_404(self):
        self.assert_404(self.owner_a.post(API + f"owner/students/{self.student_b.pk}/claim-code/"), "claim code")

    def test_no_library_b_row_appears_in_any_list_report_or_export(self):
        today = timezone.localdate()
        for path in (
            "owner/members/",
            "owner/members/?status=current",
            "owner/members/?search=Bhavna",
            "owner/dues/",
            "owner/payments/",
            "owner/complaints/",
            "owner/visits/",
            "owner/attendance/",
            "owner/attendance/live/",
            "owner/seats/",
            "owner/dashboard/",
            "owner/reports/occupancy/",
            f"owner/reports/revenue/?from={today - timedelta(days=30)}&to={today}",
            "owner/reports/complaints/",
            "owner/reports/domains/",
            "owner/audit-log/",
            "notifications/",
            "owner/exports/members.csv",
            "owner/exports/payments.csv",
            "owner/exports/attendance.csv",
        ):
            response = self.owner_a.get(API + path)
            self.assertEqual(response.status_code, 200, f"{path}: {response.status_code}")
            text = b"".join(response.streaming_content).decode() if response.streaming else response.content.decode()
            self.assert_no_b_rows(text, path)

    def test_admission_lookup_masks_another_librarys_student(self):
        response = self.owner_a.post(
            API + "owner/admissions/lookup/", {"phone": self.student_b.phone, "email": ""}, format="json"
        )
        text = response.content.decode()
        self.assertNotIn(self.student_b.phone, text)
        self.assertNotIn("bhavna.bee@example.com", text)


class PositiveControlTests(IsolationWorld):
    """The absence checks above only mean something if the same rows are visible to their rightful owner."""

    def test_owner_b_and_student_b_do_see_their_own_rows(self):
        for path, needles in (
            ("owner/members/", [str(self.member_b.pk), "Bhavna Bee"]),
            ("owner/payments/", [str(self.payment_b.pk)]),
            ("owner/complaints/", [str(self.complaint_b.pk)]),
            ("owner/visits/", [str(self.visit_b.pk)]),
            ("owner/attendance/", [str(self.record_b.pk)]),
            ("owner/seats/", [str(self.seat_b.pk)]),
        ):
            text = self.owner_b.get(API + path).content.decode()
            for needle in needles:
                self.assertIn(needle, text, f"owner B should see {needle} in {path}")
        for path, needle in (
            ("student/memberships/", str(self.member_b.pk)),
            ("student/payments/", str(self.payment_b.pk)),
            ("student/complaints/", str(self.complaint_b.pk)),
        ):
            self.assertIn(needle, self.me_b.get(API + path).content.decode(), path)
        self.assertEqual(self.owner_b.get(API + f"owner/members/{self.member_b.pk}/").status_code, 200)
        self.assertEqual(self.me_b.get(API + f"student/payments/{self.payment_b.pk}/").status_code, 200)


class StudentAgainstOtherStudentTests(IsolationWorld):
    """SECURITY.md 6.3: Student A against Student B's ids."""

    def test_detail_endpoints_are_404(self):
        self.assert_404(self.me_a.get(API + f"student/memberships/{self.member_b.pk}/"), "membership detail")
        self.assert_404(self.me_a.get(API + f"student/payments/{self.payment_b.pk}/"), "payment detail")
        self.assert_404(self.me_a.get(API + f"student/complaints/{self.complaint_b.pk}/"), "complaint detail")

    def test_orders_and_verification_for_someone_elses_hold_membership_or_order_are_404(self):
        self.assert_404(
            self.me_a.post(API + "payments/orders/", {"hold_id": str(self.hold_b.pk)}, format="json"),
            "order for B's hold",
        )
        self.assert_404(
            self.me_a.post(API + "payments/orders/", {"membership_id": str(self.member_b.pk)}, format="json"),
            "renewal order for B's membership",
        )
        payments_before = Payment.objects.count()
        forged = self.gateway.checkout_signature(self.order_b["order_id"], "pay_stolen")
        self.assert_404(
            self.me_a.post(
                API + "payments/verify/",
                {
                    "razorpay_order_id": self.order_b["order_id"],
                    "razorpay_payment_id": "pay_stolen",
                    "razorpay_signature": forged,
                },
                format="json",
            ),
            "verify B's order with a valid signature",
        )
        self.assertEqual(Payment.objects.count(), payments_before)
        self.assertEqual(Payment.objects.get(gateway_order_id=self.order_b["order_id"]).status, "pending")

    def test_cancelling_someone_elses_hold_or_visit_is_404_and_changes_nothing(self):
        self.assert_404(self.me_a.post(API + f"student/holds/{self.hold_b.pk}/cancel/"), "cancel hold")
        self.assert_404(self.me_a.post(API + f"student/visits/{self.visit_b.pk}/cancel/"), "cancel visit")
        self.hold_b.refresh_from_db()
        self.visit_b.refresh_from_db()
        self.assertEqual(self.hold_b.status, SeatHold.Status.PENDING)
        self.assertEqual(self.visit_b.status, "pending")

    def test_marking_someone_elses_notification_read_is_404(self):
        self.assert_404(self.me_a.post(API + f"notifications/{self.notification_b.pk}/read/"), "mark read")
        self.notification_b.refresh_from_db()
        self.assertIsNone(self.notification_b.read_at)

    def test_checking_in_needs_the_callers_own_membership_at_that_library(self):
        before = AttendanceRecord.objects.count()
        response = self.me_a.post(
            API + "student/attendance/check-in/", {"library_id": str(self.lib_b.pk)}, format="json"
        )
        self.assertIn(response.status_code, (403, 404, 409), response.content)
        self.assertEqual(AttendanceRecord.objects.count(), before)
        self.assertFalse(AttendanceRecord.objects.filter(student=self.student_a).exists())

    def test_a_complaint_needs_a_membership_at_that_library(self):
        response = self.me_a.post(
            API + "student/complaints/",
            {"library_id": str(self.lib_b.pk), "category": "ac", "description": "I was never a member here, yet."},
            format="json",
        )
        self.assertEqual(response.json()["error_code"], "NO_ACTIVE_MEMBERSHIP", response.content)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Complaint.objects.filter(student=self.student_a).exists())

    def test_no_student_b_row_appears_in_any_student_a_list(self):
        for path in (
            "student/memberships/?include_archived=true",
            "student/payments/",
            "student/complaints/",
            "student/visits/",
            "student/attendance/",
            "student/attendance/current/",
            "student/holds/current/",
            "student/dashboard/",
            "notifications/",
        ):
            response = self.me_a.get(API + path)
            self.assertEqual(response.status_code, 200, f"{path}: {response.status_code}")
            self.assert_no_b_rows(response.content.decode(), path)

    def test_the_public_seat_map_never_exposes_who_holds_or_occupies_a_seat(self):
        for library in (self.lib_a, self.lib_b):
            response = client_for(make_student()).get(API + f"libraries/{library.pk}/seats/")
            self.assertEqual(response.status_code, 200)
            text = json.dumps(response.json())
            for needle in (
                "Bhavna",
                "bhavna.bee",
                "Hari Hold",
                "hari.hold",
                self.student_b.phone,
                str(self.student_b.pk),
                str(self.holder_b.pk),
                str(self.student_a.pk),
            ):
                self.assertNotIn(needle, text)

    def test_the_library_page_never_returns_personal_data(self):
        text = self.client_anonymous().get(API + f"libraries/{self.lib_b.pk}/").content.decode()
        for needle in ("bhavna.bee", "Bhavna", "hari.hold", self.student_b.phone):
            self.assertNotIn(needle, text)

    def client_anonymous(self):
        from rest_framework.test import APIClient

        return APIClient()


class MalformedIdentifierTests(IsolationWorld):
    """SECURITY.md 7: identifiers are validated by the URL converters; unknown ones are plain 404s."""

    def test_unknown_uuids_are_404_for_both_roles(self):
        ghost = uuid.uuid4()
        self.assert_404(self.owner_a.get(API + f"owner/members/{ghost}/"), "owner unknown member")
        self.assert_404(self.me_a.get(API + f"student/payments/{ghost}/"), "student unknown payment")
        self.assert_404(self.me_a.post(API + f"notifications/{ghost}/read/"), "unknown notification")

    def test_a_malformed_id_is_a_404_not_a_500(self):
        self.assertEqual(self.owner_a.get(API + "owner/members/not-a-uuid/").status_code, 404)
        self.assertEqual(self.me_a.get(API + "student/payments/12345/").status_code, 404)
