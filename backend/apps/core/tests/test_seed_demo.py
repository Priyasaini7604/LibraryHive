"""The demo seed: real code paths, idempotent, and never in production (T26)."""

import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.complaints.models import Complaint
from apps.libraries.models import Library
from apps.memberships import selectors
from apps.memberships.models import Membership
from apps.payments.models import Payment
from apps.visits.models import VisitRequest


def seed(**kwargs):
    out = io.StringIO()
    call_command("seed_demo", stdout=out, **kwargs)
    return out.getvalue()


@override_settings(DEBUG=True, ENVIRONMENT="local")
class SeedDemoTests(TestCase):
    def test_creates_a_working_demo_library(self):
        text = seed()
        self.assertIn("owner@demo.libraryhive.test", text)
        library = Library.objects.get(owner__email="owner@demo.libraryhive.test")
        self.assertTrue(library.is_published)
        self.assertEqual(Membership.objects.filter(library=library).count(), 6)
        self.assertEqual(Payment.objects.filter(library=library, status="success").count(), 6)
        statuses = {m.status for m in selectors.owner_members(library)}
        self.assertEqual(statuses, {"active", "due", "overdue"})
        self.assertEqual(AttendanceRecord.objects.filter(library=library, status="open").count(), 2)
        self.assertEqual(Complaint.objects.count(), 1)
        self.assertEqual(VisitRequest.objects.count(), 1)
        self.assertTrue(User.objects.get(email="aarav@demo.libraryhive.test").check_password("Demo-pass-12345"))

    def test_running_it_again_changes_nothing(self):
        seed()
        counts = (User.objects.count(), Membership.objects.count(), Payment.objects.count(), Library.objects.count())
        seed()
        self.assertEqual(
            counts, (User.objects.count(), Membership.objects.count(), Payment.objects.count(), Library.objects.count())
        )

    def test_the_demo_feeds_the_scheduled_jobs(self):
        seed()
        from apps.core import jobs

        summary = jobs.run_steps()
        self.assertTrue(summary["ok"])
        by_name = {s["name"]: s for s in summary["steps"]}
        self.assertGreaterEqual(by_name["renewal_notifications"]["created"], 3)


class SeedDemoSafetyTests(TestCase):
    @override_settings(DEBUG=True, ENVIRONMENT="production")
    def test_never_in_production(self):
        with self.assertRaises(CommandError):
            seed()
        self.assertFalse(User.objects.exists())

    @override_settings(DEBUG=False, ENVIRONMENT="staging")
    def test_needs_debug_or_force_elsewhere(self):
        with self.assertRaises(CommandError):
            seed()
        seed(force=True)
        self.assertTrue(User.objects.filter(email="owner@demo.libraryhive.test").exists())
