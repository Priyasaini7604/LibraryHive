"""Role matrix over every route (SECURITY.md section 20, RBAC): no owner or student endpoint is open to the wrong role.

The test walks the real URL configuration, so a new endpoint is covered the moment it is added:
- an anonymous caller gets 401 on every `owner/` and `student/` route;
- a student gets 403 on every `owner/` route;
- an owner gets 403 on every `student/` route.
Permissions are checked before any validation, so empty bodies are enough.
"""

import re
import uuid

from django.test import TestCase
from django.urls import get_resolver
from rest_framework.test import APIClient

from apps.core.tests.factories import make_owner, make_student
from apps.core.tests.test_route_inventory import _api_views
from apps.libraries.tests.base import make_library

SKIP_METHODS = {"options", "head", "trace"}


def _routes(prefix: str):
    for route, name, view_class in _api_views(get_resolver().url_patterns):
        path = route.removeprefix("api/v1/") if route.startswith("api/v1/") else route
        if not path.startswith(prefix):
            continue
        methods = [m for m in view_class.http_method_names if m not in SKIP_METHODS and hasattr(view_class, m)]
        url = "/api/v1/" + re.sub(r"<[^>]+>", lambda _: str(uuid.uuid4()), path)
        yield name, url, methods


def _call(client: APIClient, method: str, url: str):
    return getattr(client, method)(url, {}, format="json") if method != "get" else client.get(url)


class RoleMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        make_library(cls.owner)
        cls.student = make_student()

    def client_as(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def check(self, prefix: str, user, expected: int):
        seen = 0
        for name, url, methods in _routes(prefix):
            for method in methods:
                with self.subTest(route=name, method=method):
                    response = _call(self.client_as(user), method, url)
                    self.assertEqual(
                        response.status_code, expected, f"{method.upper()} {url} -> {response.status_code}"
                    )
                seen += 1
        self.assertGreater(seen, 0, f"no routes found under {prefix}")

    def test_the_walk_really_finds_the_endpoints(self):
        owner_routes = {name for name, _, _ in _routes("owner/")}
        student_routes = {name for name, _, _ in _routes("student/")}
        for expected in (
            "owner-dashboard",
            "owner-member-list",
            "attendance-owner-live",
            "export-payments",
            "owner-seat-list",
        ):
            self.assertIn(expected, owner_routes)
        for expected in ("student-dashboard", "attendance-check-in", "complaint-student-list"):
            self.assertIn(expected, student_routes)

    def test_anonymous_callers_are_refused_everywhere(self):
        self.check("owner/", None, 401)
        self.check("student/", None, 401)

    def test_students_cannot_reach_owner_endpoints(self):
        self.check("owner/", self.student, 403)

    def test_owners_cannot_reach_student_endpoints(self):
        self.check("student/", self.owner, 403)

    def test_payment_creation_and_verification_are_student_only(self):
        for url in ("/api/v1/payments/orders/", "/api/v1/payments/verify/"):
            self.assertEqual(self.client_as(None).post(url, {}, format="json").status_code, 401)
            self.assertEqual(self.client_as(self.owner).post(url, {}, format="json").status_code, 403)

    def test_notifications_belong_to_the_signed_in_user_only(self):
        for url in ("/api/v1/notifications/", "/api/v1/notifications/unread-count/"):
            self.assertEqual(self.client_as(None).get(url).status_code, 401)
