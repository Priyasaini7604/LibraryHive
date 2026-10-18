"""Owner library create, read and edit (#17-#19) and the publish rule (LIB-07)."""

from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction

from apps.core.models import AuditLog
from apps.libraries import services
from apps.libraries.models import Library

from .base import LIBRARY_PAYLOAD, LibraryTestCase, make_library, make_owner, make_plan, make_student


class CreateLibraryTests(LibraryTestCase):
    def test_owner_creates_library_unpublished_with_normalised_fields(self):
        owner = make_owner()
        response = self.as_user(owner).post(self.api("owner/library/"), LIBRARY_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["name"], "Silent Hive Library")
        self.assertEqual(data["contact_phone"], "+919876543210")
        self.assertEqual(data["contact_email"], "hello@silenthive.example")
        self.assertEqual(data["latitude"], 25.4358)
        self.assertEqual({d["code"] for d in data["domains"]}, {"upsc"})
        self.assertEqual({a["code"] for a in data["amenities"]}, {"wifi", "ac"})
        self.assertFalse(data["is_published"])
        self.assertEqual(
            data["publish_checklist"],
            {"has_profile": True, "has_location": True, "has_active_plan": False, "has_active_seat": False},
        )
        library = Library.objects.get(owner=owner)
        self.assertEqual(AuditLog.objects.get(action="library.create").library_id, library.pk)

    def test_only_one_library_per_owner(self):
        owner = make_owner()
        client = self.as_user(owner)
        self.assertEqual(client.post(self.api("owner/library/"), LIBRARY_PAYLOAD, format="json").status_code, 201)
        again = client.post(self.api("owner/library/"), LIBRARY_PAYLOAD, format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["error_code"], "LIBRARY_EXISTS")
        self.assertEqual(Library.objects.filter(owner=owner).count(), 1)

    def test_students_and_anonymous_are_rejected(self):
        self.assertEqual(self.client.post(self.api("owner/library/"), LIBRARY_PAYLOAD, format="json").status_code, 401)
        student = make_student()
        response = self.as_user(student).post(self.api("owner/library/"), LIBRARY_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Library.objects.exists())

    def test_validation_errors(self):
        client = self.as_user(make_owner())
        for override, field in [
            ({"name": ""}, "name"),
            ({"latitude": 91}, "latitude"),
            ({"longitude": 181}, "longitude"),
            ({"contact_phone": "12345"}, "contact_phone"),
            ({"contact_email": "nope"}, "contact_email"),
            ({"description": "x" * 2001}, "description"),
        ]:
            response = client.post(self.api("owner/library/"), {**LIBRARY_PAYLOAD, **override}, format="json")
            self.assertEqual(response.status_code, 400, override)
            self.assertIn(field, response.json()["details"], override)

    def test_coordinates_must_be_paired(self):
        client = self.as_user(make_owner())
        payload = {**LIBRARY_PAYLOAD, "longitude": None}
        response = client.post(self.api("owner/library/"), payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("latitude", response.json()["details"])

    def test_library_without_coordinates_is_allowed(self):
        payload = {**LIBRARY_PAYLOAD, "latitude": None, "longitude": None}
        response = self.as_user(make_owner()).post(self.api("owner/library/"), payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["data"]["publish_checklist"]["has_location"])

    def test_unknown_vocabulary_codes_are_rejected(self):
        client = self.as_user(make_owner())
        response = client.post(
            self.api("owner/library/"), {**LIBRARY_PAYLOAD, "domain_codes": ["upsc", "nope"]}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("domain_codes", response.json()["details"])
        self.assertFalse(Library.objects.exists())

    def test_nested_plans_and_seats_are_ignored(self):
        payload = {**LIBRARY_PAYLOAD, "pricing_plans": [{"name": "x"}], "initial_seats": 50}
        response = self.as_user(make_owner()).post(self.api("owner/library/"), payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Library.objects.get().plans.exists())


class ReadAndEditLibraryTests(LibraryTestCase):
    def test_get_without_library_is_library_required(self):
        response = self.as_user(make_owner()).get(self.api("owner/library/"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "LIBRARY_REQUIRED")

    def test_patch_without_library_is_library_required(self):
        response = self.as_user(make_owner()).patch(self.api("owner/library/"), {"name": "X Y"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "LIBRARY_REQUIRED")

    def test_get_returns_own_library(self):
        library = make_library()
        response = self.as_user(library.owner).get(self.api("owner/library/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["id"], str(library.pk))

    def test_patch_updates_subset_and_records_diff(self):
        library = make_library()
        response = self.as_user(library.owner).patch(
            self.api("owner/library/"),
            {"name": "Renamed Hive", "amenity_codes": ["wifi"], "contact_phone": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        library.refresh_from_db()
        self.assertEqual(library.name, "Renamed Hive")
        self.assertIsNone(library.contact_phone)
        self.assertEqual(library.address, LIBRARY_PAYLOAD["address"])
        self.assertEqual(set(library.amenities.values_list("code", flat=True)), {"wifi"})
        row = AuditLog.objects.get(action="library.update")
        self.assertEqual(row.changes["name"], ["Silent Hive Library", "Renamed Hive"])
        self.assertEqual(row.changes["amenity_codes"], [["ac", "wifi"], ["wifi"]])
        self.assertEqual(row.library_id, library.pk)

    def test_patch_can_clear_both_coordinates_but_not_one(self):
        library = make_library()
        client = self.as_user(library.owner)
        one = client.patch(self.api("owner/library/"), {"latitude": None}, format="json")
        self.assertEqual(one.status_code, 400)
        both = client.patch(self.api("owner/library/"), {"latitude": None, "longitude": None}, format="json")
        self.assertEqual(both.status_code, 200)
        library.refresh_from_db()
        self.assertIsNone(library.latitude)

    def test_edit_validates_like_create(self):
        library = make_library()
        response = self.as_user(library.owner).patch(self.api("owner/library/"), {"latitude": 123}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_student_cannot_edit(self):
        library = make_library()
        response = self.as_user(make_student()).patch(self.api("owner/library/"), {"name": "Hacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        library.refresh_from_db()
        self.assertEqual(library.name, "Silent Hive Library")


class PublishRuleTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        self.library = make_library()
        self.owner = self.library.owner

    def seats(self, count):
        return mock.patch("apps.libraries.selectors.active_seat_count", return_value=count)

    def test_needs_plan_and_seat(self):
        with self.seats(3):
            services.refresh_publish_state(self.library)
            self.assertFalse(self.library.is_published)
            make_plan(self.library)
            self.library.refresh_from_db()
            self.assertTrue(self.library.is_published)
            self.assertIsNotNone(self.library.published_at)
        with self.seats(0):
            services.refresh_publish_state(self.library)
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)
        self.assertIsNone(self.library.published_at)

    def test_without_seats_a_library_never_publishes(self):
        make_plan(self.library)
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)

    def test_deactivating_last_plan_unpublishes(self):
        with self.seats(1):
            plan = make_plan(self.library)
            self.library.refresh_from_db()
            self.assertTrue(self.library.is_published)
            services.deactivate_plan(library=self.library, plan=plan, actor=self.owner)
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)

    def test_clearing_location_unpublishes(self):
        with self.seats(1):
            make_plan(self.library)
            services.update_library(library=self.library, actor=self.owner, data={"latitude": None, "longitude": None})
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)

    def test_inactive_library_is_never_published(self):
        with self.seats(1):
            make_plan(self.library)
            Library.objects.filter(pk=self.library.pk).update(is_active=False)
            self.library.refresh_from_db()
            services.refresh_publish_state(self.library)
        self.library.refresh_from_db()
        self.assertFalse(self.library.is_published)

    def test_database_refuses_published_without_coordinates(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Library.objects.filter(pk=self.library.pk).update(is_published=True, latitude=None, longitude=None)

    def test_database_refuses_single_coordinate(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Library.objects.filter(pk=self.library.pk).update(latitude=Decimal("10"), longitude=None)

    def test_checklist_reports_each_condition(self):
        client = self.as_user(self.owner)
        with self.seats(2):
            make_plan(self.library)
            data = client.get(self.api("owner/library/")).json()["data"]
        self.assertTrue(data["is_published"])
        self.assertTrue(all(data["publish_checklist"].values()))
