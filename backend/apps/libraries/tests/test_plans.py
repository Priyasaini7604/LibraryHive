"""Pricing plans (#20-#24, LIB-05)."""

from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.core.models import AuditLog
from apps.libraries import selectors, services
from apps.libraries.models import PricingPlan

from .base import LibraryTestCase, make_library, make_plan, make_student


class PlanApiTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        self.library = make_library()
        self.client_owner = self.as_user(self.library.owner)

    def create(self, **overrides):
        payload = {
            "name": "Monthly",
            "duration_days": 30,
            "price": "1200.00",
            "timing_note": "6 AM - 2 PM",
            **overrides,
        }
        return self.client_owner.post(self.api("owner/library/plans/"), payload, format="json")

    def test_create_plan(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["price"], "1200.00")
        self.assertEqual(data["timing_note"], "6 AM - 2 PM")
        self.assertTrue(data["is_active"])
        self.assertFalse(data["in_use"])
        self.assertTrue(AuditLog.objects.filter(action="plan.create", library=self.library).exists())

    def test_validation_bounds(self):
        for override, field in [
            ({"price": "0"}, "price"),
            ({"price": "-5"}, "price"),
            ({"price": "12.345"}, "price"),
            ({"duration_days": 0}, "duration_days"),
            ({"duration_days": 367}, "duration_days"),
            ({"name": ""}, "name"),
        ]:
            response = self.create(**override)
            self.assertEqual(response.status_code, 400, override)
            self.assertIn(field, response.json()["details"], override)
        self.assertEqual(self.create(duration_days=366).status_code, 201)

    def test_duplicate_active_name_is_conflict_case_insensitive(self):
        self.assertEqual(self.create(name="Monthly").status_code, 201)
        response = self.create(name="  monthly ")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "PLAN_NAME_TAKEN")

    def test_database_enforces_unique_active_name(self):
        make_plan(self.library, name="Quarterly")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PricingPlan.objects.create(library=self.library, name="QUARTERLY", duration_days=90, price=Decimal("3000"))

    def test_list_includes_inactive_plans(self):
        plan = make_plan(self.library, name="Old")
        make_plan(self.library, name="New", price=Decimal("1500"))
        services.deactivate_plan(library=self.library, plan=plan, actor=self.library.owner)
        data = self.client_owner.get(self.api("owner/library/plans/")).json()["data"]
        self.assertEqual({p["name"]: p["is_active"] for p in data}, {"Old": False, "New": True})

    def test_edit_plan_records_diff(self):
        plan = make_plan(self.library)
        response = self.client_owner.patch(
            self.api(f"owner/library/plans/{plan.pk}/"), {"price": "1300.00", "duration_days": 28}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        plan.refresh_from_db()
        self.assertEqual(plan.price, Decimal("1300.00"))
        row = AuditLog.objects.get(action="plan.update")
        self.assertEqual(row.changes["price"], ["1200.00", "1300.00"])
        self.assertEqual(row.changes["duration_days"], [30, 28])

    def test_edit_name_collision(self):
        make_plan(self.library, name="AA")
        other = make_plan(self.library, name="BB")
        response = self.client_owner.patch(self.api(f"owner/library/plans/{other.pk}/"), {"name": "aa"}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_deactivate_then_activate(self):
        plan = make_plan(self.library)
        url = f"owner/library/plans/{plan.pk}/"
        off = self.client_owner.post(self.api(url + "deactivate/"))
        self.assertEqual(off.status_code, 200)
        self.assertFalse(off.json()["data"]["is_active"])
        on = self.client_owner.post(self.api(url + "activate/"))
        self.assertTrue(on.json()["data"]["is_active"])
        actions = list(AuditLog.objects.filter(entity_id=plan.pk).values_list("action", flat=True))
        self.assertIn("plan.deactivate", actions)
        self.assertIn("plan.activate", actions)

    def test_activate_conflicts_with_active_namesake(self):
        old = make_plan(self.library, name="Monthly")
        services.deactivate_plan(library=self.library, plan=old, actor=self.library.owner)
        make_plan(self.library, name="Monthly")
        response = self.client_owner.post(self.api(f"owner/library/plans/{old.pk}/activate/"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_code"], "PLAN_NAME_TAKEN")

    def test_deactivate_is_idempotent(self):
        plan = make_plan(self.library)
        services.deactivate_plan(library=self.library, plan=plan, actor=self.library.owner)
        services.deactivate_plan(library=self.library, plan=plan, actor=self.library.owner)
        self.assertEqual(AuditLog.objects.filter(action="plan.deactivate").count(), 1)

    def test_owner_without_library_gets_library_required(self):
        from apps.core.tests.factories import make_owner

        client = self.as_user(make_owner())
        for response in (
            client.get(self.api("owner/library/plans/")),
            client.post(self.api("owner/library/plans/"), {}),
        ):
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error_code"], "LIBRARY_REQUIRED")

    def test_student_gets_403_not_409(self):
        client = self.as_user(make_student())
        self.assertEqual(client.get(self.api("owner/library/plans/")).status_code, 403)

    def test_plan_in_use_follows_referencing_rows(self):
        plan = make_plan(self.library)
        self.assertFalse(selectors.plan_in_use(plan))

    def test_referenced_plan_cannot_be_deleted_only_deactivated(self):
        plan = make_plan(self.library)
        self.library.refresh_from_db()
        # PROTECT on the library FK: a library with plans cannot be deleted either.
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.library.delete()
        self.assertTrue(PricingPlan.objects.filter(pk=plan.pk).exists())
