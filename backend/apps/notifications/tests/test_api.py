"""Notification centre API #58-#61 (NOT-02): every user reads and changes only their own."""

import uuid
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.factories import make_owner, make_student
from apps.notifications import services

BASE = "/api/v1/notifications/"


class NotificationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.student = make_student()
        self.owner = make_owner()

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def add(self, user, key, **overrides):
        values = {"type": "booking_confirmed", "title": f"Title {key}", "body": "Body", **overrides}
        return services.notify(recipient=user, dedup_key=key, **values)

    def test_everything_requires_login(self):
        anonymous = APIClient()
        for response in (
            anonymous.get(BASE),
            anonymous.get(BASE + "unread-count/"),
            anonymous.post(BASE + "read-all/"),
            anonymous.post(f"{BASE}{uuid.uuid4()}/read/"),
        ):
            self.assertEqual(response.status_code, 401)

    def test_inbox_lists_only_my_notifications_newest_first(self):
        first = self.add(self.student, "a")
        second = self.add(self.student, "b")
        self.add(self.owner, "c")
        self.add(make_student(), "d")
        data = self.client_for(self.student).get(BASE).json()["data"]
        self.assertEqual([item["id"] for item in data["items"]], [str(second.pk), str(first.pk)])
        self.assertEqual((data["page"], data["total"]), (1, 2))
        self.assertEqual(
            set(data["items"][0]), {"id", "type", "title", "body", "entity_type", "entity_id", "created_at", "read_at"}
        )

    def test_owners_use_the_same_endpoints_for_their_own_notifications(self):
        self.add(self.owner, "o1", type="visit_requested")
        data = self.client_for(self.owner).get(BASE).json()["data"]
        self.assertEqual([item["type"] for item in data["items"]], ["visit_requested"])

    def test_unread_filter_and_pagination(self):
        notes = [self.add(self.student, f"k{i}") for i in range(5)]
        services.mark_read(user=self.student, notification_id=notes[0].pk)
        client = self.client_for(self.student)
        unread = client.get(BASE, {"unread": "true"}).json()["data"]
        self.assertEqual(unread["total"], 4)
        page = client.get(BASE, {"page": 2, "page_size": 2}).json()["data"]
        self.assertEqual((page["page"], page["page_size"], len(page["items"]), page["total"]), (2, 2, 2, 5))
        self.assertEqual(client.get(BASE, {"unread": "maybe"}).status_code, 400)

    def test_unread_count_tracks_reads(self):
        a, _b = self.add(self.student, "a"), self.add(self.student, "b")
        self.add(self.owner, "other")
        client = self.client_for(self.student)
        self.assertEqual(client.get(BASE + "unread-count/").json()["data"], {"count": 2})
        client.post(f"{BASE}{a.pk}/read/")
        self.assertEqual(client.get(BASE + "unread-count/").json()["data"], {"count": 1})

    def test_mark_read_is_idempotent_and_keeps_the_first_time(self):
        note = self.add(self.student, "a")
        client = self.client_for(self.student)
        first = client.post(f"{BASE}{note.pk}/read/")
        self.assertEqual(first.status_code, 200)
        first_read = first.json()["data"]["read_at"]
        self.assertIsNotNone(first_read)
        second = client.post(f"{BASE}{note.pk}/read/")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["data"]["read_at"], first_read)

    def test_someone_elses_notification_is_404_and_stays_unread(self):
        note = self.add(self.owner, "private")
        for user in (self.student, make_owner()):
            response = self.client_for(user).post(f"{BASE}{note.pk}/read/")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error_code"], "NOT_FOUND")
        note.refresh_from_db()
        self.assertIsNone(note.read_at)

    def test_unknown_id_is_404(self):
        self.assertEqual(self.client_for(self.student).post(f"{BASE}{uuid.uuid4()}/read/").status_code, 404)

    def test_read_all_changes_only_my_unread_rows(self):
        mine = [self.add(self.student, f"m{i}") for i in range(3)]
        services.mark_read(user=self.student, notification_id=mine[0].pk)
        theirs = self.add(self.owner, "theirs")
        response = self.client_for(self.student).post(BASE + "read-all/")
        self.assertEqual(response.json()["data"], {"updated": 2})
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)
        self.assertEqual(self.client_for(self.student).post(BASE + "read-all/").json()["data"], {"updated": 0})

    def test_read_at_is_set_to_now(self):
        note = self.add(self.student, "a")
        before = timezone.now() - timedelta(seconds=5)
        services.mark_read(user=self.student, notification_id=note.pk)
        note.refresh_from_db()
        self.assertGreater(note.read_at, before)
