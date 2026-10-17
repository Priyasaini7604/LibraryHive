"""Shared helpers for account API tests."""

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

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
