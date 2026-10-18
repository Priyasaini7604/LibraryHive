"""Owner claim codes (#55, T06b) and the whole walk-in story: admitted by the owner, later claimed by the student."""

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountClaim, User
from apps.core.models import AuditLog
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for


class ClaimCodeTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)

    def admit(self, phone="9123456780", name="Ravi Walkin", seat=None):
        response = self.owner.post(
            "/api/v1/owner/admissions/",
            {
                "student": {"name": name, "phone": phone},
                "seat_id": str((seat or self.seat).pk),
                "plan_id": str(self.plan.pk),
                "payment": {"method": "cash"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["data"]

    def issue(self, student_id, client=None):
        return (client or self.owner).post(f"/api/v1/owner/students/{student_id}/claim-code/")

    def test_issues_a_one_time_code_that_is_hashed_at_rest_and_not_cached(self):
        admitted = self.admit()
        response = self.issue(admitted["student"]["id"])
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(len(data["code"]), 8)
        claim = AccountClaim.objects.get(user_id=admitted["student"]["id"], status="pending")
        self.assertEqual(claim.channel, "owner_code")
        self.assertNotIn(data["code"], str(claim.__dict__))  # only a hash is stored
        entry = AuditLog.objects.get(action="claim.code_issued")
        self.assertNotIn(data["code"], str(entry.changes))

    def test_a_new_code_revokes_the_previous_one(self):
        student_id = self.admit()["student"]["id"]
        first = self.issue(student_id).json()["data"]["code"]
        second = self.issue(student_id).json()["data"]["code"]
        self.assertNotEqual(first, second)
        pending = AccountClaim.objects.filter(user_id=student_id, channel="owner_code", status="pending")
        self.assertEqual(pending.count(), 1)

    def test_a_student_with_no_membership_here_is_a_404(self):
        outsider = User.objects.create_user(
            email=None, name="Outsider", role="student", phone="+919123456781", is_offline=True
        )
        self.assertEqual(self.issue(outsider.pk).status_code, 404)
        other_library, other_plan, other_seats = bookable_library()
        make_membership(library=other_library, plan=other_plan, student=outsider, seat=other_seats[0])
        self.assertEqual(self.issue(outsider.pk).status_code, 404)  # a membership elsewhere does not count

    def test_an_archived_membership_still_allows_a_code(self):
        student_id = self.admit()["student"]["id"]
        Membership.objects.filter(student_id=student_id).update(state="archived", archived_at=timezone.now())
        self.assertEqual(self.issue(student_id).status_code, 201)

    def test_an_online_student_cannot_be_issued_a_code(self):
        online = make_student()
        make_membership(library=self.library, plan=self.plan, student=online, seat=self.seats[1])
        response = self.issue(online.pk)
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "CONFLICT"))

    def test_roles_and_isolation(self):
        student_id = self.admit()["student"]["id"]
        self.assertEqual(self.issue(student_id, client_for(self.student)).status_code, 403)
        self.assertEqual(self.issue(student_id, APIClient()).status_code, 401)
        stranger = client_for(bookable_library()[0].owner)
        self.assertEqual(self.issue(student_id, stranger).status_code, 404)

    def test_the_walk_in_student_claims_the_account_and_keeps_everything(self):
        cache.clear()
        student_id = self.admit()["student"]["id"]
        code = self.issue(student_id).json()["data"]["code"]
        before = (Membership.objects.get(student_id=student_id).pk, Payment.objects.get(student_id=student_id).pk)

        claimed = APIClient().post(
            "/api/v1/auth/claim/complete/",
            {"phone": "9123456780", "code": code, "password": "Str0ng-pass-123", "email": "ravi@example.com"},
            format="json",
            HTTP_ORIGIN=settings.FRONTEND_URL,
        )
        self.assertEqual(claimed.status_code, 200, claimed.content)
        user = User.objects.get(pk=student_id)
        self.assertEqual((user.is_offline, user.email), (False, "ravi@example.com"))
        after = (Membership.objects.get(student_id=student_id).pk, Payment.objects.get(student_id=student_id).pk)
        self.assertEqual(after, before)  # the same User row, so every record is still attached

        signed_in = APIClient()
        signed_in.credentials(HTTP_AUTHORIZATION=f"Bearer {claimed.json()['data']['access']}")
        memberships = signed_in.get("/api/v1/student/memberships/").json()["data"]
        self.assertEqual([m["id"] for m in memberships], [str(before[0])])
        receipt = signed_in.get(f"/api/v1/student/payments/{before[1]}/").json()["data"]
        self.assertTrue(receipt["receipt_number"].startswith("LH-"))

        again = APIClient().post(
            "/api/v1/auth/claim/complete/",
            {"phone": "9123456780", "code": code, "password": "Another-pass-456"},
            format="json",
            HTTP_ORIGIN=settings.FRONTEND_URL,
        )
        self.assertIn(again.status_code, (400, 409))  # a code works once
