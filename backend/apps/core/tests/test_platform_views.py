"""Health (#1), vocabularies (#2, #3) and schema (#5)."""

from unittest import mock

from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.models import Amenity, Domain
from apps.core.tests.factories import make_student


class PlatformViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_health_ok(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "ok")
        self.assertEqual(response.json()["data"]["db"], "ok")

    def test_health_reports_database_failure_as_503(self):
        with mock.patch("apps.core.views.connection.cursor", side_effect=DatabaseError("down")):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error_code"], "SERVICE_UNAVAILABLE")

    def test_domains_are_seeded_and_public(self):
        response = self.client.get("/api/v1/meta/domains/")
        self.assertEqual(response.status_code, 200)
        codes = [item["code"] for item in response.json()["data"]]
        self.assertEqual(codes[:4], ["upsc", "ssc", "neet", "jee"])
        self.assertEqual(set(response.json()["data"][0]), {"code", "name"})

    def test_inactive_vocabulary_is_hidden(self):
        Domain.objects.filter(code="cat").update(is_active=False)
        Amenity.objects.filter(code="parking").update(is_active=False)
        domains = [d["code"] for d in self.client.get("/api/v1/meta/domains/").json()["data"]]
        amenities = [a["code"] for a in self.client.get("/api/v1/meta/amenities/").json()["data"]]
        self.assertNotIn("cat", domains)
        self.assertNotIn("parking", amenities)
        self.assertIn("wifi", amenities)

    def test_schema_is_public_outside_production(self):
        response = self.client.get("/api/v1/schema/", {"format": "json"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("openapi", response.json())

    @override_settings(SCHEMA_PUBLIC=False)
    def test_schema_is_staff_only_in_production(self):
        self.assertEqual(self.client.get("/api/v1/schema/").status_code, 401)
        self.client.force_authenticate(make_student())
        self.assertEqual(self.client.get("/api/v1/schema/").status_code, 403)
