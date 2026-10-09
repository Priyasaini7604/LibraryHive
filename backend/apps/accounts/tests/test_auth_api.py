"""Auth API (BACKEND_ARCHITECTURE.md #6-#11, SEC-1, SECURITY.md section 20 "Auth")."""

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student

PASSWORD = "Str0ng-pass-123"
COOKIE = settings.REFRESH_COOKIE_NAME


class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_ORIGIN=settings.FRONTEND_URL)

    def post(self, path, data=None, **extra):
        return self.client.post(f"/api/v1/auth/{path}", data or {}, format="json", **extra)

    def register(self, **overrides):
        payload = {
            "role": "student",
            "name": "Asha Rao",
            "email": "asha@example.com",
            "phone": "98765 43210",
            "password": PASSWORD,
            **overrides,
        }
        return self.post("register/", payload)

    def login(self, email="asha@example.com", password=PASSWORD):
        return self.post("login/", {"email": email, "password": password})

    def use_access(self, access):
        self.client.credentials(HTTP_ORIGIN=settings.FRONTEND_URL, HTTP_AUTHORIZATION=f"Bearer {access}")

    def assertError(self, response, status, code):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json()["error_code"], code)


class RegisterTests(AuthTestCase):
    def test_student_registration_signs_in_with_cookie(self):
        response = self.register(domain_code="upsc")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["user"]["email"], "asha@example.com")
        self.assertEqual(data["user"]["phone"], "+919876543210")
        self.assertEqual(data["user"]["domain"], {"code": "upsc", "name": "UPSC"})
        self.assertNotIn("has_library", data["user"])
        self.assertNotIn("refresh", data)
        self.assertNotIn(PASSWORD, response.content.decode())

        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/v1/auth/")

        self.use_access(data["access"])
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["data"]["email"], "asha@example.com")

    def test_owner_registration_reports_no_library(self):
        response = self.register(role="owner", email="owner@example.com", phone="9811122233")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIs(response.json()["data"]["user"]["has_library"], False)

    def test_owner_cannot_choose_exam_domain(self):
        self.assertError(self.register(role="owner", domain_code="upsc"), 400, "VALIDATION_ERROR")

    def test_unknown_domain_rejected(self):
        response = self.register(domain_code="astrology")
        self.assertError(response, 400, "VALIDATION_ERROR")
        self.assertIn("domain_code", response.json()["details"])

    def test_weak_password_rejected_by_django_validators(self):
        response = self.register(password="password")
        self.assertError(response, 400, "VALIDATION_ERROR")
        self.assertIn("password", response.json()["details"])

    def test_invalid_phone_rejected(self):
        response = self.register(phone="12345")
        self.assertError(response, 400, "VALIDATION_ERROR")
        self.assertIn("phone", response.json()["details"])

    def test_duplicate_email_case_insensitive(self):
        make_student(email="asha@example.com")
        self.assertError(self.register(email="ASHA@example.com"), 409, "EMAIL_TAKEN")

    def test_duplicate_phone_in_another_format(self):
        make_student(phone="+919876543210")
        self.assertError(self.register(phone="+91-98765-43210"), 409, "PHONE_TAKEN")

    def test_offline_record_requires_claim_and_creates_nothing(self):
        offline = User.objects.create_user(
            email="walkin@gmail.com", name="Walk In", role="student", is_offline=True, phone="+919876543210"
        )
        response = self.register(email="new@example.com")
        self.assertError(response, 409, "CLAIM_REQUIRED")
        self.assertEqual(
            response.json()["details"], {"channels": ["email_otp", "owner_code"], "masked_email": "w***@gmail.com"}
        )
        self.assertEqual(User.objects.count(), 1)
        offline.refresh_from_db()
        self.assertTrue(offline.is_offline)
        self.assertFalse(offline.has_usable_password())

    def test_offline_record_without_email_offers_owner_code_only(self):
        User.objects.create_user(email=None, name="Walk In", role="student", is_offline=True, phone="+919876543210")
        response = self.register()
        self.assertError(response, 409, "CLAIM_REQUIRED")
        self.assertEqual(response.json()["details"], {"channels": ["owner_code"]})

    def test_phone_and_email_of_different_accounts_conflict(self):
        User.objects.create_user(email=None, name="Walk In", role="student", is_offline=True, phone="+919876543210")
        make_student(email="asha@example.com")
        self.assertError(self.register(), 409, "IDENTITY_CONFLICT")

    def test_owner_signup_with_offline_students_phone_is_a_duplicate(self):
        User.objects.create_user(email=None, name="Walk In", role="student", is_offline=True, phone="+919876543210")
        self.assertError(self.register(role="owner", email="owner@example.com"), 409, "PHONE_TAKEN")

    def test_names_are_never_used_for_matching(self):
        make_student(name="Asha Rao", email="other@example.com", phone="+919800000001")
        self.assertEqual(self.register(name="Asha Rao").status_code, 201)


class OriginAndContentTypeTests(AuthTestCase):
    def test_missing_origin_rejected(self):
        self.client.credentials()
        self.assertError(self.register(), 403, "ORIGIN_NOT_ALLOWED")

    def test_foreign_origin_rejected(self):
        self.client.credentials(HTTP_ORIGIN="https://evil.example.com")
        with self.assertLogs("apps.security", level="WARNING") as logs:
            self.assertError(self.login(), 403, "ORIGIN_NOT_ALLOWED")
        self.assertIn("security.origin_rejected", logs.output[0])

    def test_form_encoded_body_rejected(self):
        response = self.client.post("/api/v1/auth/refresh/", {"x": "1"})  # multipart, not JSON
        self.assertError(response, 415, "UNSUPPORTED_MEDIA_TYPE")


class LoginTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.student = make_student(email="asha@example.com", password=PASSWORD, name="Asha Rao")

    def test_login_returns_access_with_claims_and_sets_cookie(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.content)
        access = AccessToken(response.json()["data"]["access"])
        self.assertEqual(access["user_id"], str(self.student.pk))
        self.assertEqual(access["role"], "student")
        self.assertEqual(access["name"], "Asha Rao")
        self.assertEqual(int(access["exp"]) - int(access["iat"]), 3600)
        self.assertIn(COOKIE, response.cookies)

    def test_email_is_case_insensitive(self):
        self.assertEqual(self.login(email="  ASHA@Example.com ").status_code, 200)

    def test_every_failure_is_the_same_generic_error(self):
        offline = User.objects.create_user(
            email="off@example.com", name="Off", role="student", is_offline=True, phone="+919811100009"
        )
        inactive = make_student(email="gone@example.com", password=PASSWORD)
        inactive.is_active = False
        inactive.save()
        attempts = [
            ("asha@example.com", "wrong-password"),
            ("nobody@example.com", PASSWORD),
            (offline.email, ""),
            ("gone@example.com", PASSWORD),
        ]
        bodies = set()
        for email, password in attempts:
            response = self.login(email=email, password=password or "anything-at-all")
            self.assertError(response, 401, "INVALID_CREDENTIALS")
            self.assertNotIn(COOKIE, response.cookies)
            bodies.add(response.json()["error"])
        self.assertEqual(bodies, {"Email or password is incorrect."})

    def test_failed_login_is_logged_with_masked_email(self):
        with self.assertLogs("apps.security", level="WARNING") as logs:
            self.login(password="wrong-password")
        record = logs.records[0]
        self.assertEqual(record.getMessage(), "auth.login_failed")

    def test_login_is_throttled_per_ip(self):
        for _ in range(10):
            self.login(password="wrong-password")
        response = self.login()
        self.assertError(response, 429, "RATE_LIMITED")
        self.assertIn("Retry-After", response)


class RefreshAndLogoutTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.student = make_student(email="asha@example.com", password=PASSWORD)
        self.login_response = self.login()
        self.first_cookie = self.login_response.cookies[COOKIE].value

    def test_refresh_rotates_cookie_and_returns_new_access(self):
        response = self.post("refresh/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(set(response.json()["data"]), {"access"})
        self.assertNotEqual(response.cookies[COOKIE].value, self.first_cookie)
        self.use_access(response.json()["data"]["access"])
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 200)

    def test_reusing_a_rotated_refresh_token_fails_and_clears_cookie(self):
        self.post("refresh/")
        self.client.cookies[COOKIE] = self.first_cookie
        response = self.post("refresh/")
        self.assertError(response, 401, "TOKEN_INVALID")
        self.assertEqual(response.cookies[COOKIE].value, "")

    def test_refresh_without_cookie_fails(self):
        self.client.cookies.clear()
        self.assertError(self.post("refresh/"), 401, "TOKEN_INVALID")

    def test_refresh_rejected_for_deactivated_user(self):
        self.student.is_active = False
        self.student.save()
        self.assertError(self.post("refresh/"), 401, "TOKEN_INVALID")

    def test_logout_blacklists_refresh_token_and_clears_cookie(self):
        self.use_access(self.login_response.json()["data"]["access"])
        response = self.post("logout/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.cookies[COOKIE].value, "")
        self.client.cookies[COOKIE] = self.first_cookie
        self.assertError(self.post("refresh/"), 401, "TOKEN_INVALID")

    def test_logout_requires_authentication_and_is_idempotent(self):
        self.assertError(self.post("logout/"), 401, "NOT_AUTHENTICATED")
        self.use_access(self.login_response.json()["data"]["access"])
        self.assertEqual(self.post("logout/").status_code, 200)
        self.assertEqual(self.post("logout/").status_code, 200)

    def test_logout_ignores_another_users_cookie(self):
        other = make_student(email="other@example.com", password=PASSWORD)
        other_cookie = self.login(email=other.email).cookies[COOKIE].value
        self.use_access(self.login_response.json()["data"]["access"])
        self.client.cookies[COOKIE] = other_cookie
        self.post("logout/")
        self.client.cookies[COOKIE] = other_cookie
        self.assertEqual(self.post("refresh/").status_code, 200)


class ProfileTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.student = make_student(email="asha@example.com", password=PASSWORD, phone="+919811100010")
        self.use_access(self.login().json()["data"]["access"])

    def patch(self, data):
        return self.client.patch("/api/v1/auth/me/", data, format="json")

    def test_me_requires_authentication(self):
        self.client.credentials()
        self.assertError(self.client.get("/api/v1/auth/me/"), 401, "NOT_AUTHENTICATED")

    def test_update_name_phone_and_domain_with_audit(self):
        response = self.patch({"name": "Asha R.", "phone": "98111 00011", "domain_code": "neet"})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual((data["name"], data["phone"], data["domain"]["code"]), ("Asha R.", "+919811100011", "neet"))
        entry = AuditLog.objects.get(action="profile.update")
        self.assertEqual(entry.actor, self.student)
        self.assertEqual(entry.changes["name"][1], "Asha R.")
        self.assertEqual(entry.changes["phone"], ["+919811100010", "+919811100011"])
        self.assertEqual(entry.changes["domain"], [None, "neet"])

    def test_email_is_not_editable(self):
        self.patch({"email": "hijack@example.com", "name": "Asha"})
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "asha@example.com")

    def test_phone_taken_by_someone_else(self):
        make_student(phone="+919811100099")
        self.assertError(self.patch({"phone": "9811100099"}), 409, "PHONE_TAKEN")

    def test_domain_can_be_cleared(self):
        self.patch({"domain_code": "upsc"})
        response = self.patch({"domain_code": None})
        self.assertIsNone(response.json()["data"]["domain"])

    def test_owner_cannot_set_domain(self):
        owner = make_owner(email="o@example.com", password=PASSWORD)
        self.use_access(self.login(email=owner.email).json()["data"]["access"])
        self.assertError(self.patch({"domain_code": "upsc"}), 400, "VALIDATION_ERROR")

    def test_no_change_writes_no_audit(self):
        self.patch({"name": self.student.name})
        self.assertFalse(AuditLog.objects.filter(action="profile.update").exists())
