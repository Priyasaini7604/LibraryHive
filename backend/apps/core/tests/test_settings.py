"""Configuration safety (SECURITY.md sections 5 and 13)."""

from django.conf import settings
from django.test import SimpleTestCase

from config.settings.guard import unsafe_settings_errors

SAFE = {
    "debug": False,
    "secret_key": "s" * 60,
    "jwt_signing_key": "j" * 60,
    "allowed_hosts": ["api.libraryhive.example"],
    "cors_allowed_origins": ["https://libraryhive.example"],
    "environment": "production",
    "razorpay_key_id": "rzp_live_abc",
}


class ProductionGuardTests(SimpleTestCase):
    def test_safe_settings_pass(self):
        self.assertEqual(unsafe_settings_errors(**SAFE), [])

    def test_each_unsafe_value_is_reported(self):
        cases = {
            "debug": True,
            "secret_key": "django-insecure-" + "x" * 60,
            "jwt_signing_key": "short",
            "allowed_hosts": ["*"],
            "cors_allowed_origins": ["*"],
            "razorpay_key_id": "rzp_test_abc",
        }
        for field, bad_value in cases.items():
            with self.subTest(field=field):
                self.assertTrue(unsafe_settings_errors(**{**SAFE, field: bad_value}))

    def test_jwt_key_must_differ_from_secret_key(self):
        self.assertTrue(unsafe_settings_errors(**{**SAFE, "jwt_signing_key": SAFE["secret_key"]}))

    def test_email_notifications_need_a_backend_that_really_delivers(self):
        console = "django.core.mail.backends.console.EmailBackend"
        smtp = "django.core.mail.backends.smtp.EmailBackend"
        for backend in (
            console,
            "django.core.mail.backends.locmem.EmailBackend",
            "django.core.mail.backends.dummy.EmailBackend",
            "django.core.mail.backends.filebased.EmailBackend",
        ):
            with self.subTest(backend=backend):
                errors = unsafe_settings_errors(**SAFE, email_notifications_enabled=True, email_backend=backend)
                self.assertEqual(len(errors), 1)
                self.assertIn("EMAIL_NOTIFICATIONS_ENABLED", errors[0])
        self.assertEqual(unsafe_settings_errors(**SAFE, email_notifications_enabled=True, email_backend=smtp), [])
        # Switched off, any backend is fine: no delivery rows are created and nothing is marked sent.
        self.assertEqual(unsafe_settings_errors(**SAFE, email_notifications_enabled=False, email_backend=console), [])

    def test_test_keys_allowed_in_staging(self):
        self.assertEqual(
            unsafe_settings_errors(**{**SAFE, "environment": "staging", "razorpay_key_id": "rzp_test_abc"}), []
        )


class RuntimeSettingsTests(SimpleTestCase):
    def test_postgresql_is_the_database(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")

    def test_default_permission_is_deny(self):
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"], ("rest_framework.permissions.IsAuthenticated",)
        )

    def test_jwt_lifetimes_match_security_design(self):
        jwt = settings.SIMPLE_JWT
        self.assertEqual(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds(), 3600)
        self.assertEqual(jwt["REFRESH_TOKEN_LIFETIME"].days, 7)
        self.assertTrue(jwt["ROTATE_REFRESH_TOKENS"])
        self.assertTrue(jwt["BLACKLIST_AFTER_ROTATION"])
        self.assertNotEqual(jwt["SIGNING_KEY"], settings.SECRET_KEY)

    def test_business_timezone(self):
        self.assertEqual(settings.TIME_ZONE, "Asia/Kolkata")
        self.assertTrue(settings.USE_TZ)

    def test_cors_never_allows_credentials_or_wildcard(self):
        self.assertFalse(settings.CORS_ALLOW_CREDENTIALS)
        self.assertNotIn("*", settings.CORS_ALLOWED_ORIGINS)
