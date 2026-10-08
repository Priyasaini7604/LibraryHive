"""Request IDs, JSON logs and redaction (LOG-01, LOG-02, LOG-08)."""

import json
import logging

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.logging import REDACTED, ContextFilter, JsonFormatter, RedactionFilter, mask_text, redact
from apps.core.tests.factories import make_owner


@override_settings(ROOT_URLCONF="apps.core.tests.urls")
class RequestIdTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_generated_request_id_is_returned(self):
        response = self.client.get("/api/v1/_test/ok/")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")
        self.assertEqual(response.json()["request_id"], response["X-Request-ID"])

    def test_valid_incoming_request_id_is_echoed(self):
        response = self.client.get("/api/v1/_test/ok/", HTTP_X_REQUEST_ID="client-abc-12345")
        self.assertEqual(response["X-Request-ID"], "client-abc-12345")

    def test_unsafe_incoming_request_id_is_replaced(self):
        response = self.client.get("/api/v1/_test/ok/", HTTP_X_REQUEST_ID="bad id <script>")
        self.assertNotEqual(response["X-Request-ID"], "bad id <script>")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_access_log_line_per_request(self):
        with self.assertLogs("apps.http", level="INFO") as logs:
            self.client.get("/api/v1/_test/ok/")
        record = logs.records[0]
        self.assertEqual(record.getMessage(), "http.request")
        self.assertEqual(record.status, 200)
        self.assertEqual(record.method, "GET")
        self.assertGreaterEqual(record.duration_ms, 0)

    def test_access_log_records_authenticated_user(self):
        owner = make_owner()
        self.client.force_authenticate(owner)
        with self.assertLogs("apps.http", level="INFO") as logs:
            self.client.get("/api/v1/_test/owner-only/")
        self.assertEqual(logs.records[0].user_id, str(owner.pk))


class RedactionTests(SimpleTestCase):
    def test_masks_email_and_phone_in_text(self):
        text = mask_text("login failed for rahul.sharma@gmail.com phone +919876543210")
        self.assertIn("r***@gmail.com", text)
        self.assertIn("+9198******10", text)
        self.assertNotIn("rahul.sharma", text)
        self.assertNotIn("9876543210", text)

    def test_drops_sensitive_keys_recursively(self):
        data = redact(
            {
                "password": "hunter2",
                "nested": {"refresh": "eyJ...", "otp": "123456", "ok": "fine"},
                "Authorization": "Bearer abc",
            }
        )
        self.assertEqual(data["password"], REDACTED)
        self.assertEqual(data["nested"]["refresh"], REDACTED)
        self.assertEqual(data["nested"]["otp"], REDACTED)
        self.assertEqual(data["Authorization"], REDACTED)
        self.assertEqual(data["nested"]["ok"], "fine")

    def test_identifiers_are_not_masked(self):
        uuid_like = "12345678-1234-1234-1234-123456789012"
        self.assertEqual(redact(uuid_like, "seat_id"), uuid_like)
        self.assertEqual(redact("123456789012345", "request_id"), "123456789012345")

    def test_json_line_contains_context_and_redacted_extras(self):
        logger = logging.getLogger("apps.test.redaction")
        record = logger.makeRecord(
            logger.name,
            logging.WARNING,
            __file__,
            1,
            "auth.login_failed for a@b.com",
            None,
            None,
            extra={"email": "student@example.com", "password": "hunter2", "seat_id": "abc"},
        )
        ContextFilter().filter(record)
        RedactionFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["level"], "WARNING")
        self.assertEqual(payload["event"], "auth.login_failed for a***@b.com")
        self.assertEqual(payload["email"], "s***@example.com")
        self.assertEqual(payload["password"], REDACTED)
        self.assertEqual(payload["seat_id"], "abc")
        for key in ("ts", "logger", "request_id", "user_id", "library_id"):
            self.assertIn(key, payload)
        self.assertNotIn("hunter2", json.dumps(payload))
