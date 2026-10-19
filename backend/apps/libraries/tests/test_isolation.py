"""Tenant isolation (SECURITY.md 6.4, AUTH-08): Owner A never reaches Library B."""

from apps.core.exceptions import NotFound
from apps.core.mixins import OwnerLibraryScopedMixin
from apps.core.permissions import HasLibrary
from apps.libraries.models import PricingPlan

from .base import LibraryTestCase, make_library, make_plan


class IsolationTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        self.lib_a = make_library()
        self.lib_b = make_library(name="Other Library")
        self.plan_a = make_plan(self.lib_a, name="A plan")
        self.plan_b = make_plan(self.lib_b, name="B plan")
        self.owner_a = self.as_user(self.lib_a.owner)

    def test_plan_list_shows_only_own_plans(self):
        names = [p["name"] for p in self.owner_a.get(self.api("owner/library/plans/")).json()["data"]]
        self.assertEqual(names, ["A plan"])

    def test_other_librarys_plan_is_404_on_every_object_endpoint(self):
        base = f"owner/library/plans/{self.plan_b.pk}/"
        responses = [
            self.owner_a.patch(self.api(base), {"price": "1.00"}, format="json"),
            self.owner_a.post(self.api(base + "deactivate/")),
            self.owner_a.post(self.api(base + "activate/")),
        ]
        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error_code"], "NOT_FOUND")
        self.plan_b.refresh_from_db()
        self.assertTrue(self.plan_b.is_active)
        self.assertEqual(str(self.plan_b.price), "1200.00")

    def test_library_endpoints_never_expose_another_library(self):
        self.assertEqual(self.owner_a.get(self.api("owner/library/")).json()["data"]["id"], str(self.lib_a.pk))
        self.owner_a.patch(self.api("owner/library/"), {"name": "Mine Now"}, format="json")
        self.lib_b.refresh_from_db()
        self.assertEqual(self.lib_b.name, "Other Library")


class ScopedMixinTests(LibraryTestCase):
    def test_owner_mixin_scopes_queryset_and_hides_foreign_ids(self):
        lib_a, lib_b = make_library(), make_library()
        plan_a, plan_b = make_plan(lib_a), make_plan(lib_b)

        class Probe(OwnerLibraryScopedMixin):
            model = PricingPlan

            class request:
                user = lib_a.owner

        probe = Probe()
        self.assertEqual(list(probe.get_queryset()), [plan_a])
        self.assertEqual(probe.get_scoped_object(pk=plan_a.pk), plan_a)
        with self.assertRaises(NotFound):
            probe.get_scoped_object(pk=plan_b.pk)

    def test_has_library_permission(self):
        from apps.core.exceptions import Conflict
        from apps.core.tests.factories import make_owner, make_student

        class FakeRequest:
            def __init__(self, user):
                self.user = user

        self.assertTrue(HasLibrary().has_permission(FakeRequest(make_library().owner), None))
        with self.assertRaises(Conflict):
            HasLibrary().has_permission(FakeRequest(make_owner()), None)
        self.assertFalse(HasLibrary().has_permission(FakeRequest(make_student()), None))
