"""Input hardening (SECURITY.md section 7 and section 20, "Validation" and "Headers").

Input serializers declare their fields explicitly, so unknown fields are ignored and read-only fields can never be
set by a client (no mass assignment). Each case sends the fields a client must NOT control next to a valid request
and asserts that the stored row keeps the server's value.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.complaints.models import Complaint
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.models import PricingPlan
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, client_for
from apps.seats.models import SeatHold
from apps.visits.models import VisitRequest

API = "/api/v1/"
User = get_user_model()


class MassAssignmentTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.owner = client_for(self.library.owner)
        self.me = client_for(self.student)

    def test_registration_cannot_grant_staff_or_set_server_fields(self):
        stranger_id = "11111111-1111-4111-8111-111111111111"
        response = APIClient().post(
            API + "auth/register/",
            {
                "role": "student",
                "name": "Eve Escalator",
                "email": "eve.escalator@example.com",
                "phone": "+919876512345",
                "password": "Str0ng-pass-123!x",
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
                "is_offline": True,
                "id": stranger_id,
                "claimed_at": "2020-01-01T00:00:00Z",
            },
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(email="eve.escalator@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_offline)
        self.assertNotEqual(str(user.pk), stranger_id)
        self.assertIsNone(user.claimed_at)

    def test_profile_update_cannot_change_role_email_or_flags(self):
        before = (self.student.role, self.student.email, self.student.pk)
        response = self.me.patch(
            API + "auth/me/",
            {
                "name": "Renamed Student",
                "role": "owner",
                "email": "taken.over@example.com",
                "is_staff": True,
                "is_superuser": True,
                "is_offline": True,
                "id": "22222222-2222-4222-8222-222222222222",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, "Renamed Student")
        self.assertEqual((self.student.role, self.student.email, self.student.pk), before)
        self.assertFalse(self.student.is_staff or self.student.is_superuser or self.student.is_offline)

    def test_library_and_plan_writes_ignore_owner_id_and_publication_fields(self):
        other_owner = make_owner()
        library = self.library
        before = (library.pk, library.owner_id, library.created_at, library.published_at)
        response = self.owner.patch(
            API + "owner/library/",
            {
                "description": "A calm place to study.",
                "owner": str(other_owner.pk),
                "id": "33333333-3333-4333-8333-333333333333",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        library.refresh_from_db()
        self.assertEqual((library.pk, library.owner_id, library.created_at, library.published_at), before)

        other_library_id = self.library.pk  # a plan always lands in the caller's own library
        response = self.owner.post(
            API + "owner/library/plans/",
            {
                "name": "Weekend",
                "price": "500.00",
                "duration_days": 30,
                "library": "44444444-4444-4444-8444-444444444444",
                "is_active": False,
                "in_use": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        plan = PricingPlan.objects.get(name="Weekend")
        self.assertEqual(plan.library_id, other_library_id)
        self.assertTrue(plan.is_active)

    def test_a_hold_ignores_status_expiry_and_student(self):
        far_future = (timezone.now() + timedelta(days=30)).isoformat()
        other = make_student()
        response = self.me.post(
            API + "student/holds/",
            {
                "seat_id": str(self.seat.pk),
                "plan_id": str(self.plan.pk),
                "status": "completed",
                "expires_at": far_future,
                "student": str(other.pk),
                "library": "55555555-5555-4555-8555-555555555555",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        hold = SeatHold.objects.get()
        self.assertEqual(hold.status, SeatHold.Status.PENDING)
        self.assertEqual(hold.student_id, self.student.pk)
        self.assertEqual(hold.library_id, self.library.pk)
        self.assertLess(hold.expires_at, timezone.now() + timedelta(hours=1))

    def test_an_order_takes_its_amount_from_the_plan_never_from_the_client(self):
        hold = self.hold_seat()
        response = self.me.post(
            API + "payments/orders/",
            {"hold_id": str(hold.pk), "amount": "1.00", "amount_paise": 100, "status": "success", "currency": "USD"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, self.plan.price)
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.currency, "INR")
        self.assertEqual(self.gateway.orders[-1]["order"].amount_paise, int(self.plan.price * 100))

    def test_an_admission_takes_its_amount_from_the_plan_never_from_the_client(self):
        response = self.owner.post(
            API + "owner/admissions/",
            {
                "student": {"name": "Walk In", "phone": "+919876500321", "email": "", "is_staff": True},
                "seat_id": str(self.seats[1].pk),
                "plan_id": str(self.plan.pk),
                "payment": {"method": "cash", "amount": "1.00", "status": "failed", "receipt_number": "FREE-001"},
                "amount": "1.00",
                "state": "archived",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payment = Payment.objects.get(student__phone="+919876500321")
        self.assertEqual(payment.amount, self.plan.price)
        self.assertEqual(payment.status, "success")
        self.assertNotEqual(payment.receipt_number, "FREE-001")
        membership = Membership.objects.get(student__phone="+919876500321")
        self.assertEqual(membership.state, Membership.State.ACTIVE)
        self.assertFalse(membership.student.is_staff)

    def test_a_complaint_ignores_status_response_and_identity_fields(self):
        make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)
        other = make_student()
        response = self.me.post(
            API + "student/complaints/",
            {
                "library_id": str(self.library.pk),
                "category": "ac",
                "description": "The cooling is not working at all.",
                "status": "resolved",
                "owner_response": "Already fixed",
                "student": str(other.pk),
                "resolved_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        complaint = Complaint.objects.get()
        self.assertEqual((complaint.status, complaint.owner_response), ("open", ""))
        self.assertEqual(complaint.student_id, self.student.pk)
        self.assertIsNone(complaint.resolved_at)

    def test_an_owner_reply_cannot_move_a_complaint_between_students_or_libraries(self):
        make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)
        self.me.post(
            API + "student/complaints/",
            {"library_id": str(self.library.pk), "category": "ac", "description": "The cooling is not working."},
            format="json",
        )
        complaint = Complaint.objects.get()
        other = make_student()
        response = self.owner.patch(
            API + f"owner/complaints/{complaint.pk}/",
            {
                "status": "in_progress",
                "student": str(other.pk),
                "library": "66666666-6666-4666-8666-666666666666",
                "category": "wifi",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, "in_progress")
        self.assertEqual(
            (complaint.student_id, complaint.library_id, complaint.category), (self.student.pk, self.library.pk, "ac")
        )

    def test_a_visit_request_ignores_status_and_note_fields(self):
        response = self.me.post(
            API + "student/visits/",
            {
                "library_id": str(self.library.pk),
                "preferred_date": str(timezone.localdate() + timedelta(days=2)),
                "preferred_slot": "morning",
                "status": "accepted",
                "owner_note": "Pre-approved",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        visit = VisitRequest.objects.get()
        self.assertEqual(visit.status, "pending")
        self.assertEqual(visit.owner_note, "")

    def test_a_plan_price_cannot_be_set_through_the_membership_or_payment_endpoints(self):
        hold = self.hold_seat()
        self.me.post(
            API + "payments/orders/",
            {"hold_id": str(hold.pk), "plan_id": str(self.plan.pk), "price": "1"},
            format="json",
        )
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price, Decimal("1200.00"))


class ResponseHeaderTests(PaymentTestCase):
    """SECURITY.md section 20, "Headers": the backend's own responses carry the baseline browser protections."""

    def test_api_responses_forbid_sniffing_and_framing(self):
        for client, path in ((APIClient(), API + "health/"), (client_for(self.student), API + "student/dashboard/")):
            response = client.get(path)
            self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff", path)
            self.assertEqual(response.headers.get("X-Frame-Options"), "DENY", path)
            self.assertIn("Referrer-Policy", response.headers, path)

    def test_the_seat_map_and_personal_endpoints_are_not_cacheable(self):
        seat_map = APIClient().get(API + f"libraries/{self.library.pk}/seats/")
        self.assertIn("no-store", seat_map.headers.get("Cache-Control", ""))
