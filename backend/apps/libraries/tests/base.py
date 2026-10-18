"""Shared helpers for library tests."""

from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests.factories import make_owner, make_student
from apps.libraries import services
from apps.libraries.models import Library, PricingPlan

LIBRARY_PAYLOAD = {
    "name": "Silent Hive Library",
    "description": "A quiet place to prepare.",
    "address": "12 Civil Lines",
    "city": "Prayagraj",
    "area": "Civil Lines",
    "latitude": 25.4358,
    "longitude": 81.8463,
    "contact_phone": "98765 43210",
    "contact_email": "Hello@Silenthive.example",
    "opens_at": "06:00",
    "closes_at": "22:00",
    "operating_notes": "Open 24x7 during exams",
    "domain_codes": ["upsc"],
    "amenity_codes": ["wifi", "ac"],
}


def make_library(owner=None, *, publish=False, **overrides) -> Library:
    owner = owner or make_owner()
    data = {**LIBRARY_PAYLOAD, **overrides}
    data["latitude"] = Decimal(str(data["latitude"])) if data.get("latitude") is not None else None
    data["longitude"] = Decimal(str(data["longitude"])) if data.get("longitude") is not None else None
    library = services.create_library(owner=owner, data=data)
    if publish:
        services.create_plan(
            library=library,
            actor=owner,
            data={"name": "Monthly", "duration_days": 30, "price": Decimal("1200.00")},
        )
        with mock.patch("apps.libraries.selectors.active_seat_count", return_value=1):
            services.refresh_publish_state(library)
        library.refresh_from_db()
    return library


def make_plan(library: Library, **overrides) -> PricingPlan:
    data = {"name": "Monthly", "duration_days": 30, "price": Decimal("1200.00"), **overrides}
    return services.create_plan(library=library, actor=library.owner, data=data)


class LibraryTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(type(user).objects.get(pk=user.pk))  # fresh row, no stale cached relations
        return client

    def api(self, path):
        return f"/api/v1/{path}"


__all__ = ["LIBRARY_PAYLOAD", "LibraryTestCase", "make_library", "make_owner", "make_plan", "make_student"]
