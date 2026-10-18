"""Complaints: who may raise one, the owner's lifecycle, notifications and isolation (SPEC.md 4.10, #71-#76)."""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.complaints.models import Complaint
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.notifications.models import Notification
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for

LIST = "/api/v1/student/complaints/"
TEXT = "The air conditioning on the second floor has not worked for three days."


class ComplaintBase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.me = client_for(self.student)
        self.membership = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)

    def raise_one(self, client=None, **overrides):
        payload = {"library_id": str(self.library.pk), "category": "ac", "description": TEXT, **overrides}
        return (client or self.me).post(LIST, payload, format="json")

    def make(self):
        response = self.raise_one()
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["data"]["id"]

    def patch(self, complaint_id, client=None, **payload):
        return (client or self.owner).patch(f"/api/v1/owner/complaints/{complaint_id}/", payload, format="json")


class RaiseComplaintTests(ComplaintBase):
    def test_a_member_raises_a_complaint_and_the_owner_is_notified(self):
        response = self.raise_one()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["status"], data["category"], data["owner_response"]), ("open", "ac", ""))
        complaint = Complaint.objects.get()
        self.assertEqual((complaint.student_id, complaint.membership_id), (self.student.pk, self.membership.pk))
        note = Notification.objects.get(recipient=self.library.owner)
        self.assertEqual(note.type, "complaint_created")
        self.assertEqual(note.dedup_key, f"complaint:{complaint.pk}:open:{self.library.owner.pk}")

    def test_a_past_member_may_still_complain_and_the_latest_membership_is_linked(self):
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        self.assertEqual(self.raise_one().status_code, 201)
        newer = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seats[1])
        self.assertEqual(self.raise_one().status_code, 201)
        self.assertEqual(Complaint.objects.order_by("-created_at").first().membership_id, newer.pk)

    def test_non_members_cannot_complain(self):
        response = self.raise_one(client_for(make_student()))
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "NO_ACTIVE_MEMBERSHIP"))
        other_library, _, _ = bookable_library()
        self.assertEqual(self.raise_one(library_id=str(other_library.pk)).status_code, 409)
        self.assertFalse(Complaint.objects.exists())

    def test_validation(self):
        self.assertEqual(self.raise_one(description="too short").status_code, 400)
        self.assertEqual(self.raise_one(description="x" * 2001).status_code, 400)
        self.assertEqual(self.raise_one(category="rude").status_code, 400)
        self.assertEqual(self.me.post(LIST, {}, format="json").status_code, 400)

    def test_roles(self):
        self.assertEqual(self.raise_one(self.owner).status_code, 403)
        self.assertEqual(self.raise_one(APIClient()).status_code, 401)


class StudentViewTests(ComplaintBase):
    def test_lists_only_my_complaints_with_the_documented_row(self):
        complaint_id = self.make()
        other = make_student()
        make_membership(library=self.library, plan=self.plan, student=other, seat=self.seats[1])
        self.raise_one(client_for(other))
        items = self.me.get(LIST).json()["data"]["items"]
        self.assertEqual([row["id"] for row in items], [complaint_id])
        self.assertEqual(
            set(items[0]),
            {
                "id",
                "library",
                "category",
                "description",
                "status",
                "owner_response",
                "responded_at",
                "resolved_at",
                "created_at",
            },
        )
        self.assertEqual(self.me.get(LIST, {"status": "resolved"}).json()["data"]["items"], [])
        self.assertEqual(self.me.get(LIST, {"status": "bogus"}).status_code, 400)

    def test_detail_is_scoped_to_the_author(self):
        complaint_id = self.make()
        self.assertEqual(self.me.get(f"{LIST}{complaint_id}/").status_code, 200)
        self.assertEqual(client_for(make_student()).get(f"{LIST}{complaint_id}/").status_code, 404)


class OwnerLifecycleTests(ComplaintBase):
    def test_inbox_filters_and_isolation(self):
        complaint_id = self.make()
        rows = self.owner.get("/api/v1/owner/complaints/").json()["data"]["items"]
        self.assertEqual([r["id"] for r in rows], [complaint_id])
        self.assertEqual((rows[0]["student"]["id"], rows[0]["seat_label"]), (str(self.student.pk), "A-1"))
        self.assertEqual(self.owner.get("/api/v1/owner/complaints/", {"category": "wifi"}).json()["data"]["items"], [])
        self.assertEqual(self.owner.get("/api/v1/owner/complaints/", {"status": "open"}).json()["data"]["total"], 1)
        stranger = client_for(bookable_library()[0].owner)
        self.assertEqual(stranger.get("/api/v1/owner/complaints/").json()["data"]["items"], [])
        self.assertEqual(stranger.get(f"/api/v1/owner/complaints/{complaint_id}/").status_code, 404)
        self.assertEqual(self.patch(complaint_id, stranger, status="in_progress").status_code, 404)

    def test_open_to_in_progress_to_resolved_with_notifications_and_audit(self):
        complaint_id = self.make()
        first = self.patch(complaint_id, status="in_progress", owner_response="Technician called")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["data"]["status"], "in_progress")
        second = self.patch(complaint_id, status="resolved", owner_response="Fixed on Monday")
        self.assertEqual(second.status_code, 200, second.content)
        complaint = Complaint.objects.get()
        self.assertEqual((complaint.status, complaint.owner_response), ("resolved", "Fixed on Monday"))
        self.assertEqual((complaint.resolved_by_id, complaint.resolved_at is not None), (self.library.owner.pk, True))
        keys = set(Notification.objects.filter(recipient=self.student).values_list("dedup_key", flat=True))
        self.assertEqual(
            keys,
            {
                f"complaint:{complaint.pk}:in_progress:{self.student.pk}",
                f"complaint:{complaint.pk}:resolved:{self.student.pk}",
            },
        )
        self.assertEqual(AuditLog.objects.filter(action="complaint.update", entity_id=complaint.pk).count(), 2)

    def test_resolving_needs_a_response_and_open_can_resolve_directly(self):
        complaint_id = self.make()
        response = self.patch(complaint_id, status="resolved")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.patch(complaint_id, status="resolved", owner_response="  ").status_code, 400)
        self.assertEqual(self.patch(complaint_id, status="resolved", owner_response="Done").status_code, 200)

    def test_a_response_can_be_given_without_changing_the_status(self):
        complaint_id = self.make()
        response = self.patch(complaint_id, owner_response="We are looking into it")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual((data["status"], data["owner_response"]), ("open", "We are looking into it"))
        self.assertIsNotNone(data["responded_at"])

    def test_invalid_transitions(self):
        complaint_id = self.make()
        self.patch(complaint_id, status="in_progress")
        again = self.patch(complaint_id, status="in_progress")
        self.assertEqual(again.status_code, 400)  # no change at all
        self.patch(complaint_id, status="resolved", owner_response="Done")
        for payload in (
            {"status": "in_progress"},
            {"owner_response": "More"},
            {"status": "resolved", "owner_response": "x"},
        ):
            response = self.patch(complaint_id, **payload)
            self.assertEqual((response.status_code, response.json()["error_code"]), (409, "INVALID_TRANSITION"))
        self.assertEqual(self.patch(complaint_id, status="open").status_code, 400)  # reopening is not offered

    def test_roles_and_empty_patch(self):
        complaint_id = self.make()
        self.assertEqual(self.patch(complaint_id, self.me, status="resolved").status_code, 403)
        self.assertEqual(self.patch(complaint_id).status_code, 400)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/complaints/").status_code, 409)

    def test_the_database_forbids_a_resolved_complaint_without_a_time(self):
        complaint_id = self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Complaint.objects.filter(pk=complaint_id).update(status="resolved")
