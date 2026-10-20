"""`domain_breakdown` on the public explore page (#15, DIS-05, DASH-03): counts per exam domain, never identities."""

from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.dates import business_today
from apps.core.models import Domain
from apps.core.tests.factories import make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership

from .test_discovery import PRAYAGRAJ, published


def breakdown(library_id) -> list[dict]:
    response = APIClient().get(f"/api/v1/libraries/{library_id}/")
    assert response.status_code == 200, response.content
    return response.json()["data"]["domain_breakdown"]


class PublicDomainBreakdownTests(TestCase):
    def setUp(self):
        self.library = published("Domain Hall", *PRAYAGRAJ)
        self.upsc, self.neet = Domain.objects.get(code="upsc"), Domain.objects.get(code="neet")

    def join(self, library=None, *, domain):
        library = library or self.library
        return make_membership(library=library, plan=library.plans.first(), student=make_student(domain=domain))

    def test_no_members_gives_an_empty_list(self):
        self.assertEqual(breakdown(self.library.pk), [])

    def test_counts_current_members_per_domain_largest_first(self):
        self.join(domain=self.neet)
        self.join(domain=self.upsc)
        self.join(domain=self.upsc)
        self.assertEqual(
            breakdown(self.library.pk),
            [
                {"code": "upsc", "name": self.upsc.name, "count": 2},
                {"code": "neet", "name": self.neet.name, "count": 1},
            ],
        )

    def test_due_and_overdue_members_still_count(self):
        due = self.join(domain=self.upsc)
        overdue = self.join(domain=self.upsc)
        today = business_today()
        Membership.objects.filter(pk=due.pk).update(next_due_date=today)
        Membership.objects.filter(pk=overdue.pk).update(
            start_date=today - timedelta(days=40), next_due_date=today - timedelta(days=5)
        )
        self.assertEqual(breakdown(self.library.pk), [{"code": "upsc", "name": self.upsc.name, "count": 2}])

    def test_archived_members_and_students_without_a_domain_are_not_counted(self):
        kept = self.join(domain=self.upsc)
        gone = self.join(domain=self.upsc)
        Membership.objects.filter(pk=gone.pk).update(state=Membership.State.ARCHIVED, archived_at=timezone.now())
        make_membership(library=self.library, plan=self.library.plans.first(), student=make_student())  # no exam domain
        self.assertEqual(breakdown(self.library.pk), [{"code": "upsc", "name": self.upsc.name, "count": 1}])
        self.assertTrue(Membership.objects.filter(pk=kept.pk).exists())

    def test_another_librarys_members_do_not_leak_in(self):
        other = published("Other Hall", *PRAYAGRAJ)
        self.join(other, domain=self.neet)
        self.join(other, domain=self.neet)
        self.assertEqual(breakdown(self.library.pk), [])
        self.assertEqual(breakdown(other.pk), [{"code": "neet", "name": self.neet.name, "count": 2}])

    def test_rows_hold_only_code_name_and_count(self):
        self.join(domain=self.upsc)
        row = breakdown(self.library.pk)[0]
        self.assertEqual(set(row), {"code", "name", "count"})
        body = APIClient().get(f"/api/v1/libraries/{self.library.pk}/").content.decode()
        self.assertNotIn("student", body)

    def test_the_public_figure_equals_the_owner_dashboard_figure(self):
        self.join(domain=self.upsc)
        self.join(domain=self.neet)
        client = APIClient()
        client.force_authenticate(self.library.owner)
        owner = client.get("/api/v1/owner/dashboard/").json()["data"]["domain_breakdown"]
        self.assertEqual(breakdown(self.library.pk), owner)

    def test_one_extra_query_however_many_members(self):
        self.join(domain=self.upsc)
        with CaptureQueriesContext(connection) as few:
            breakdown(self.library.pk)
        for _ in range(5):
            self.join(domain=self.neet)
        with CaptureQueriesContext(connection) as many:
            breakdown(self.library.pk)
        self.assertEqual(len(few), len(many))

    def test_unpublished_library_is_still_404(self):
        type(self.library).objects.filter(pk=self.library.pk).update(is_published=False)
        self.assertEqual(APIClient().get(f"/api/v1/libraries/{self.library.pk}/").status_code, 404)
