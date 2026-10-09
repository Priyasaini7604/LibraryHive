"""Every response uses the standard envelope (AUTH-12, BACKEND_ARCHITECTURE.md 4.1 and 6)."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.core.exceptions import register_constraint_error
from apps.core.tests.factories import make_owner, make_student

ENVELOPE_KEYS = {"success", "data", "error", "error_code", "details", "request_id"}


@override_settings(ROOT_URLCONF="apps.core.tests.urls")
class EnvelopeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def assertEnvelope(self, response, *, status, success, code=None):
        self.assertEqual(response.status_code, status, response.content)
        body = response.json()
        self.assertEqual(set(body), ENVELOPE_KEYS)
        self.assertIs(body["success"], success)
        self.assertEqual(body["error_code"], code)
        self.assertEqual(body["request_id"], response["X-Request-ID"])
        return body

    def test_success(self):
        body = self.assertEnvelope(self.client.get("/api/v1/_test/ok/"), status=200, success=True)
        self.assertEqual(body["data"], {"hello": "world"})
        self.assertIsNone(body["error"])

    def test_validation_error_has_field_details(self):
        response = self.client.post("/api/v1/_test/validation/", {"name": "too long"}, format="json")
        body = self.assertEnvelope(response, status=400, success=False, code="VALIDATION_ERROR")
        self.assertIn("name", body["details"])
        self.assertIsInstance(body["details"]["name"][0], str)

    def test_app_error_keeps_its_code(self):
        body = self.assertEnvelope(
            self.client.get("/api/v1/_test/conflict/"), status=409, success=False, code="SEAT_UNAVAILABLE"
        )
        self.assertEqual(body["error"], "Seat is no longer available.")

    def test_unauthenticated(self):
        self.assertEnvelope(
            self.client.get("/api/v1/_test/auth-required/"), status=401, success=False, code="NOT_AUTHENTICATED"
        )

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEnvelope(
            self.client.get("/api/v1/_test/auth-required/"), status=401, success=False, code="TOKEN_INVALID"
        )

    def test_wrong_role_is_403(self):
        self.client.force_authenticate(make_student())
        with self.assertLogs("apps.security", level="WARNING") as logs:
            self.assertEnvelope(
                self.client.get("/api/v1/_test/owner-only/"), status=403, success=False, code="FORBIDDEN_ROLE"
            )
        self.assertIn("security.permission_denied", logs.output[0])

    def test_owner_passes_owner_permission(self):
        self.client.force_authenticate(make_owner())
        self.assertEnvelope(self.client.get("/api/v1/_test/owner-only/"), status=200, success=True)

    def test_unknown_route_is_404_envelope(self):
        self.assertEnvelope(self.client.get("/api/v1/does-not-exist/"), status=404, success=False, code="NOT_FOUND")

    def test_method_not_allowed(self):
        self.assertEnvelope(
            self.client.delete("/api/v1/_test/ok/"), status=405, success=False, code="METHOD_NOT_ALLOWED"
        )

    def test_throttled_is_429_with_retry_after(self):
        self.client.get("/api/v1/_test/throttled/")
        response = self.client.get("/api/v1/_test/throttled/")
        self.assertEnvelope(response, status=429, success=False, code="RATE_LIMITED")
        self.assertIn("Retry-After", response)

    def test_unexpected_error_is_generic_500_and_logged(self):
        with self.assertLogs("apps.core.errors", level="ERROR") as logs:
            response = self.client.get("/api/v1/_test/crash/")
        body = self.assertEnvelope(response, status=500, success=False, code="SERVER_ERROR")
        self.assertNotIn("hunter2", response.content.decode())
        self.assertNotIn("RuntimeError", response.content.decode())
        self.assertIsNone(body["details"])
        self.assertIn("http.error", logs.output[0])

    def test_registered_constraint_violation_becomes_409(self):
        register_constraint_error(
            "user_email_unique", code="EMAIL_TAKEN", message="An account with this email already exists."
        )
        body = self.assertEnvelope(
            self.client.post("/api/v1/_test/duplicate-email/"), status=409, success=False, code="EMAIL_TAKEN"
        )
        self.assertEqual(body["error"], "An account with this email already exists.")
