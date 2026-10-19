"""Visit requests: rules, the owner's decision, notifications and isolation (SPEC.md 4.11, #77-#81)."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.core.dates import business_today
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.notifications.models import Notification
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for
from apps.visits.models import VisitRequest

LIST = "/api/v1/student/visits/"


class VisitBase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.me = client_for(self.student)
        self.library.refresh_from_db()
        assert self.library.is_published

    def ask(self, client=None, **overrides):
        payload = {
            "library_id": str(self.library.pk),
            "preferred_date": str(business_today() + timedelta(days=3)),
            "preferred_slot": "morning",
            "student_note": "Interested in a quiet corner",
            **overrides,
        }
        return (client or self.me).post(LIST, payload, format="json")

    def make(self):
        response = self.ask()
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["data"]["id"]

    def decide(self, visit_id, client=None, **payload):
        return (client or self.owner).post(f"/api/v1/owner/visits/{visit_id}/decision/", payload, format="json")


class RequestVisitTests(VisitBase):
    def test_a_student_requests_a_visit_and_the_owner_is_notified(self):
        response = self.ask()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["status"], data["preferred_slot"], data["owner_note"]), ("pending", "morning", ""))
        visit = VisitRequest.objects.get()
        note = Notification.objects.get(recipient=self.library.owner)
        self.assertEqual(
            (note.type, note.dedup_key), ("visit_requested", f"visit:{visit.pk}:pending:{self.library.owner.pk}")
        )

    def test_one_pending_request_per_library(self):
        self.make()
        response = self.ask()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "VISIT_PENDING_EXISTS"))
        self.assertEqual(VisitRequest.objects.count(), 1)

    def test_another_student_and_another_library_are_independent(self):
        self.make()
        self.assertEqual(self.ask(client_for(make_student())).status_code, 201)
        other_library, _, _ = bookable_library()
        self.assertEqual(self.ask(library_id=str(other_library.pk)).status_code, 201)

    def test_date_window(self):
        today = business_today()
        for offset, expected in ((-1, 400), (0, 201), (61, 400)):
            student = client_for(make_student())
            response = self.ask(student, preferred_date=str(today + timedelta(days=offset)))
            self.assertEqual(response.status_code, expected, (offset, response.content))
        self.assertEqual(self.ask(preferred_date=str(today + timedelta(days=60))).status_code, 201)

    def test_unpublished_or_unknown_library(self):
        type(self.library).objects.filter(pk=self.library.pk).update(is_published=False)
        response = self.ask()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "LIBRARY_NOT_BOOKABLE"))
        self.assertEqual(
            self.ask(library_id="00000000-0000-0000-0000-000000000000").json()["error_code"], "LIBRARY_NOT_BOOKABLE"
        )

    def test_validation_and_roles(self):
        self.assertEqual(self.ask(preferred_slot="night").status_code, 400)
        self.assertEqual(self.ask(student_note="x" * 501).status_code, 400)
        self.assertEqual(self.ask(self.owner).status_code, 403)
        self.assertEqual(self.ask(APIClient()).status_code, 401)

    def test_a_new_request_is_possible_after_the_old_one_was_decided_or_cancelled(self):
        visit_id = self.make()
        self.assertEqual(self.me.post(f"{LIST}{visit_id}/cancel/").status_code, 200)
        self.assertEqual(self.ask().status_code, 201)


class StudentVisitViewTests(VisitBase):
    def test_lists_only_my_requests_and_filters_by_status(self):
        visit_id = self.make()
        self.ask(client_for(make_student()))
        items = self.me.get(LIST).json()["data"]["items"]
        self.assertEqual([row["id"] for row in items], [visit_id])
        self.assertEqual(self.me.get(LIST, {"status": "accepted"}).json()["data"]["items"], [])

    def test_cancel_only_from_pending_and_only_my_own(self):
        visit_id = self.make()
        self.assertEqual(client_for(make_student()).post(f"{LIST}{visit_id}/cancel/").status_code, 404)
        self.assertEqual(self.me.post(f"{LIST}{visit_id}/cancel/").json()["data"]["status"], "cancelled")
        again = self.me.post(f"{LIST}{visit_id}/cancel/")
        self.assertEqual((again.status_code, again.json()["error_code"]), (409, "INVALID_TRANSITION"))


class OwnerVisitTests(VisitBase):
    def test_inbox_has_the_student_and_filters(self):
        visit_id = self.make()
        rows = self.owner.get("/api/v1/owner/visits/").json()["data"]["items"]
        self.assertEqual([r["id"] for r in rows], [visit_id])
        self.assertEqual(set(rows[0]["student"]), {"id", "name", "phone"})
        day = str(business_today() + timedelta(days=3))
        get = lambda **q: self.owner.get("/api/v1/owner/visits/", q).json()["data"]["items"]  # noqa: E731
        self.assertEqual(len(get(**{"from": day, "to": day})), 1)
        self.assertEqual(get(**{"from": str(business_today() + timedelta(days=10))}), [])
        self.assertEqual(get(status="rejected"), [])

    def test_accept_and_reject_notify_the_student_and_are_audited(self):
        accepted = self.make()
        response = self.decide(accepted, decision="accept", owner_note="Come at 10")
        self.assertEqual(response.status_code, 200, response.content)
        visit = VisitRequest.objects.get(pk=accepted)
        self.assertEqual(
            (visit.status, visit.owner_note, visit.decided_by_id), ("accepted", "Come at 10", self.library.owner.pk)
        )
        self.assertIsNotNone(visit.decided_at)
        note = Notification.objects.get(recipient=self.student, type="visit_decided")
        self.assertEqual(note.dedup_key, f"visit:{visit.pk}:accepted:{self.student.pk}")
        self.assertTrue(AuditLog.objects.filter(action="visit.decide", entity_id=visit.pk).exists())

        rejected = self.make()
        self.assertEqual(self.decide(rejected, decision="reject").json()["data"]["status"], "rejected")

    def test_a_decision_is_final(self):
        visit_id = self.make()
        self.decide(visit_id, decision="accept")
        again = self.decide(visit_id, decision="reject")
        self.assertEqual((again.status_code, again.json()["error_code"]), (409, "INVALID_TRANSITION"))
        self.assertEqual(self.me.post(f"{LIST}{visit_id}/cancel/").status_code, 409)

    def test_isolation_validation_and_roles(self):
        visit_id = self.make()
        stranger = client_for(bookable_library()[0].owner)
        self.assertEqual(self.decide(visit_id, stranger, decision="accept").status_code, 404)
        self.assertEqual(stranger.get("/api/v1/owner/visits/").json()["data"]["items"], [])
        self.assertEqual(self.decide(visit_id, decision="maybe").status_code, 400)
        self.assertEqual(self.decide(visit_id, self.me, decision="accept").status_code, 403)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/visits/").status_code, 409)

    def test_the_database_allows_one_pending_per_pair_and_requires_a_decision_time(self):
        self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VisitRequest.objects.create(
                student=self.student, library=self.library, preferred_date=business_today(), preferred_slot="morning"
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            VisitRequest.objects.filter(student=self.student).update(status="accepted")
