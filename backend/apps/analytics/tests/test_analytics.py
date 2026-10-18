"""Dashboards, reports, CSV exports and the activity log (#82-#89): each number equals its list, scoped per tenant."""

import csv
import io
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.exports import safe_cell
from apps.attendance.models import AttendanceRecord
from apps.complaints.models import Complaint
from apps.core.dates import business_today
from apps.core.models import AuditLog, Domain
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for
from apps.visits.models import VisitRequest


def shift(membership, *, due_in):
    due = business_today() + timedelta(days=due_in)
    Membership.objects.filter(pk=membership.pk).update(start_date=due - timedelta(days=30), next_due_date=due)


def pay(library, plan, student, membership, *, status="success", method="cash", amount="1200.00", purpose="renewal"):
    number = Payment.objects.count() + 1
    return Payment.objects.create(
        library=library, student=student, membership=membership, plan=plan, purpose=purpose, channel="offline",
        method=method, status="success", amount=amount, recorded_by=library.owner,
        receipt_number=f"LH-2026-9{number:05d}", paid_at=timezone.now(),
        period_start=business_today(), period_end=business_today() + timedelta(days=30),
    )  # fmt: skip


def unpaid(library, plan, student, membership, *, status, amount="5000.00"):
    """A non-success online payment (the database only allows `success` for offline ones)."""
    number = Payment.objects.count() + 1
    return Payment.objects.create(
        library=library, student=student, membership=membership, plan=plan, purpose="renewal", channel="online",
        method="gateway", status=status, amount=amount, gateway_order_id=f"order_x_{number}",
        receipt_number=f"LH-2026-8{number:05d}",
    )  # fmt: skip


class Scenario(PaymentTestCase):
    """Library A (the owner under test) and library B (must never leak into A's figures)."""

    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.domain = Domain.objects.first() or Domain.objects.create(code="upsc", name="UPSC")
        self.s1, self.s2, self.s3 = (make_student(domain=self.domain), make_student(), make_student())
        self.active = make_membership(library=self.library, plan=self.plan, student=self.s1, seat=self.seats[0])
        self.due = make_membership(library=self.library, plan=self.plan, student=self.s2, seat=self.seats[1])
        shift(self.due, due_in=2)
        self.overdue = make_membership(library=self.library, plan=self.plan, student=self.s3, seat=self.seats[2])
        shift(self.overdue, due_in=-4)

        self.lib_b, self.plan_b, self.seats_b = bookable_library()
        self.b_student = make_student(domain=self.domain)
        self.b_member = make_membership(
            library=self.lib_b, plan=self.plan_b, student=self.b_student, seat=self.seats_b[0]
        )
        shift(self.b_member, due_in=-9)
        pay(self.lib_b, self.plan_b, self.b_student, self.b_member, amount="9999.00")

    def get(self, url, **query):
        return self.owner.get(url, query)


class DashboardTests(Scenario):
    def test_every_number_equals_the_list_it_summarises(self):
        pay(self.library, self.plan, self.s1, self.active, method="cash")
        pay(self.library, self.plan, self.s2, self.due, method="upi_direct", amount="800.00")
        unpaid(self.library, self.plan, self.s3, self.overdue, status="needs_refund")
        Complaint.objects.create(
            student=self.s1, library=self.library, membership=self.active, category="ac", description="x" * 12
        )
        VisitRequest.objects.create(
            student=make_student(), library=self.library, preferred_date=business_today(), preferred_slot="morning"
        )
        AttendanceRecord.objects.create(
            student=self.s1, library=self.library, membership=self.active, seat=self.seats[0], date=business_today(),
            check_in_at=timezone.now(), check_in_method="self", status="open",
        )  # fmt: skip

        data = self.get("/api/v1/owner/dashboard/").json()["data"]
        members = lambda **q: self.get("/api/v1/owner/members/", **q).json()["data"]["total"]  # noqa: E731
        self.assertEqual(
            data["members"],
            {"active": members(status="active"), "due": members(status="due"), "overdue": members(status="overdue")},
        )
        self.assertEqual(data["members"], {"active": 1, "due": 1, "overdue": 1})
        dues = self.get("/api/v1/owner/dues/").json()["data"]["total"]
        self.assertEqual(data["members"]["due"] + data["members"]["overdue"], dues)
        self.assertEqual(data["seats"], {"total": 3, "empty": 0, "reserved": 0, "occupied": 3, "disabled": 0})
        self.assertEqual(data["today"]["present_now"], len(self.get("/api/v1/owner/attendance/live/").json()["data"]))
        self.assertEqual((data["today"]["check_ins"], data["today"]["new_bookings"]), (1, 3))
        self.assertEqual(
            data["open_complaints"], self.get("/api/v1/owner/complaints/", status="open").json()["data"]["total"]
        )
        self.assertEqual(
            data["pending_visits"], self.get("/api/v1/owner/visits/", status="pending").json()["data"]["total"]
        )
        self.assertEqual(
            data["upcoming_renewals_7d"], 1
        )  # only the member due in 2 days; 20 days out and overdue are not
        self.assertEqual(data["revenue"]["this_month_total"], "2000.00")  # the needs_refund one is not revenue
        self.assertEqual(set(data["revenue"]["by_method"]), {"cash", "upi_direct"})
        self.assertEqual(data["domain_breakdown"], [{"code": self.domain.code, "name": self.domain.name, "count": 1}])
        self.assertTrue(
            data["publish_checklist"] and all(isinstance(v, bool) for v in data["publish_checklist"].values())
        )

    def test_nothing_from_the_other_library_leaks_in(self):
        data = self.get("/api/v1/owner/dashboard/").json()["data"]
        self.assertEqual(data["revenue"]["this_month_total"], "0")
        self.assertEqual(data["members"]["overdue"], 1)  # B's overdue member is not counted
        b_data = client_for(self.lib_b.owner).get("/api/v1/owner/dashboard/").json()["data"]
        self.assertEqual((b_data["revenue"]["this_month_total"], b_data["members"]["overdue"]), ("9999.00", 1))

    def test_roles(self):
        self.assertEqual(client_for(self.student).get("/api/v1/owner/dashboard/").status_code, 403)
        self.assertEqual(APIClient().get("/api/v1/owner/dashboard/").status_code, 401)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/dashboard/").status_code, 409)


class ReportTests(Scenario):
    def test_occupancy_by_row(self):
        data = self.get("/api/v1/owner/reports/occupancy/").json()["data"]
        self.assertEqual(data["counts"]["occupied"], 3)
        self.assertEqual(data["by_row"], [{"row_label": "A", "total": 3, "occupied": 3, "reserved": 0, "empty": 0}])

    def test_revenue_counts_successful_payments_only_and_validates_the_range(self):
        pay(self.library, self.plan, self.s1, self.active, amount="1200.00")
        pay(self.library, self.plan, self.s2, self.due, amount="800.00", purpose="new_membership", method="upi_direct")
        unpaid(self.library, self.plan, self.s3, self.overdue, status="failed", amount="7000.00")
        today = str(business_today())
        data = self.get("/api/v1/owner/reports/revenue/", **{"from": today, "to": today}).json()["data"]
        self.assertEqual((data["total"], data["count"]), ("2000.00", 2))
        self.assertEqual(data["by_method"]["cash"], {"total": "1200.00", "count": 1})
        self.assertEqual(data["by_purpose"]["new_membership"], {"total": "800.00", "count": 1})
        self.assertEqual(data["by_month"], [{"month": today[:7], "total": "2000.00", "count": 2}])
        long_range = self.get("/api/v1/owner/reports/revenue/", **{"from": "2025-01-01", "to": today})
        self.assertEqual(long_range.status_code, 400)
        self.assertEqual(self.get("/api/v1/owner/reports/revenue/", **{"to": today}).status_code, 400)
        self.assertEqual(
            self.get("/api/v1/owner/reports/revenue/", **{"from": today, "to": "2020-01-01"}).status_code, 400
        )

    def test_complaint_and_domain_reports(self):
        Complaint.objects.create(
            student=self.s1, library=self.library, membership=self.active, category="wifi", description="x" * 12
        )
        data = self.get("/api/v1/owner/reports/complaints/").json()["data"]
        self.assertEqual((data["by_status"], data["by_category"]), ({"open": 1}, {"wifi": 1}))
        self.assertEqual(self.get("/api/v1/owner/reports/domains/").json()["data"][0]["count"], 1)
        future = str(business_today() + timedelta(days=5))
        self.assertEqual(
            self.get("/api/v1/owner/reports/complaints/", **{"from": future}).json()["data"]["by_status"], {}
        )


class ExportTests(Scenario):
    def read(self, response):
        self.assertEqual(response.status_code, 200)
        return list(csv.reader(io.StringIO(b"".join(response.streaming_content).decode())))

    def test_members_csv_is_scoped_has_headers_and_is_audited(self):
        response = self.get("/api/v1/owner/exports/members.csv")
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", response["Content-Disposition"])
        rows = self.read(response)
        self.assertEqual(rows[0][0], "Name")
        self.assertEqual(len(rows) - 1, 3)
        names = {row[0] for row in rows[1:]}
        self.assertNotIn(self.b_student.name, names)
        self.assertTrue(AuditLog.objects.filter(action="export.members", library=self.library).exists())

    def test_member_status_filter(self):
        rows = self.read(self.get("/api/v1/owner/exports/members.csv", status="overdue"))
        self.assertEqual([row[6] for row in rows[1:]], ["overdue"])

    def test_payments_csv_is_scoped_and_filterable_by_date(self):
        pay(self.library, self.plan, self.s1, self.active)
        rows = self.read(self.get("/api/v1/owner/exports/payments.csv"))
        self.assertEqual(len(rows) - 1, 1)
        self.assertNotIn("9999.00", [row[4] for row in rows])
        future = str(business_today() + timedelta(days=3))
        self.assertEqual(len(self.read(self.get("/api/v1/owner/exports/payments.csv", **{"from": future}))), 1)

    def test_attendance_csv(self):
        AttendanceRecord.objects.create(
            student=self.s1, library=self.library, membership=self.active, seat=self.seats[0], date=business_today(),
            check_in_at=timezone.now() - timedelta(hours=2), check_out_at=timezone.now(), duration_minutes=120,
            check_in_method="self", check_out_method="self", status="closed",
        )  # fmt: skip
        rows = self.read(self.get("/api/v1/owner/exports/attendance.csv"))
        self.assertEqual((rows[0][0], len(rows) - 1, rows[1][5]), ("Date", 1, "120"))

    def test_formula_injection_is_neutralised_end_to_end(self):
        type(self.s1).objects.filter(pk=self.s1.pk).update(name='=HYPERLINK("http://evil.example","x")')
        rows = self.read(self.get("/api/v1/owner/exports/members.csv"))
        cell = next(row[0] for row in rows[1:] if "HYPERLINK" in row[0])
        self.assertTrue(cell.startswith("'="))

    def test_roles_and_bad_query(self):
        self.assertEqual(client_for(self.student).get("/api/v1/owner/exports/members.csv").status_code, 403)
        self.assertEqual(APIClient().get("/api/v1/owner/exports/payments.csv").status_code, 401)
        self.assertEqual(self.get("/api/v1/owner/exports/members.csv", status="nope").status_code, 400)


class SafeCellTests(SimpleTestCase):
    def test_dangerous_prefixes_are_quoted(self):
        for value in ("=1+1", "+1", "-1", "@SUM(A1)", "\tcmd", "\rcmd"):
            self.assertEqual(safe_cell(value), "'" + value)

    def test_plain_values_are_untouched(self):
        for value, expected in (("Asha", "Asha"), (None, ""), (12, "12"), ("a=b", "a=b")):
            self.assertEqual(safe_cell(value), expected)


class AuditLogTests(Scenario):
    def test_log_is_scoped_filterable_and_has_no_ip(self):
        self.owner.post(f"/api/v1/owner/members/{self.active.pk}/renewals/", {"method": "cash"}, format="json")
        AuditLog.objects.create(
            actor=self.lib_b.owner, library=self.lib_b, actor_role="owner", action="secret.other",
            entity_type="x", entity_id=self.lib_b.pk,
        )  # fmt: skip
        data = self.get("/api/v1/owner/audit-log/").json()["data"]
        actions = {row["action"] for row in data["items"]}
        self.assertIn("membership.renew", actions)
        self.assertNotIn("secret.other", actions)
        row = data["items"][0]
        self.assertEqual(
            set(row), {"id", "created_at", "actor", "action", "entity_type", "entity_id", "changes", "reason"}
        )
        self.assertNotIn("ip_address", str(data))
        only = self.get("/api/v1/owner/audit-log/", action="membership.renew").json()["data"]["items"]
        self.assertTrue(only and all(r["action"] == "membership.renew" for r in only))
        self.assertEqual(self.get("/api/v1/owner/audit-log/", entity_type="nothing").json()["data"]["items"], [])

    def test_roles(self):
        self.assertEqual(client_for(self.student).get("/api/v1/owner/audit-log/").status_code, 403)


class StudentDashboardTests(Scenario):
    def test_shows_only_the_students_own_data(self):
        pay(self.library, self.plan, self.s1, self.active)
        pay(self.library, self.plan, self.s2, self.due)
        Complaint.objects.create(
            student=self.s1, library=self.library, membership=self.active, category="ac", description="x" * 12
        )
        Complaint.objects.create(
            student=self.s2, library=self.library, membership=self.due, category="ac", description="x" * 12
        )
        VisitRequest.objects.create(
            student=self.s1,
            library=self.lib_b,
            preferred_date=business_today() + timedelta(days=2),
            preferred_slot="evening",
        )
        AttendanceRecord.objects.create(
            student=self.s1, library=self.library, membership=self.active, seat=self.seats[0], date=business_today(),
            check_in_at=timezone.now(), check_in_method="self", status="open",
        )  # fmt: skip
        data = client_for(self.s1).get("/api/v1/student/dashboard/").json()["data"]
        self.assertEqual([m["id"] for m in data["memberships"]], [str(self.active.pk)])
        self.assertEqual(data["current_attendance"]["status"], "open")
        self.assertEqual(len(data["recent_payments"]), 1)
        self.assertEqual(data["open_complaints"], 1)
        self.assertEqual([v["library"]["id"] for v in data["visits"]], [str(self.lib_b.pk)])
        self.assertIsNone(data["pending_hold"])

    def test_pending_hold_and_empty_state(self):
        fresh = make_student()
        data = client_for(fresh).get("/api/v1/student/dashboard/").json()["data"]
        self.assertEqual(
            data,
            {
                "memberships": [],
                "current_attendance": None,
                "recent_payments": [],
                "open_complaints": 0,
                "visits": [],
                "pending_hold": None,
            },
        )

    def test_a_live_hold_is_reported_with_its_countdown(self):
        fresh = make_student()
        seat = self.seats[0]
        Membership.objects.filter(pk=self.active.pk).update(state="archived", archived_at=timezone.now())
        hold = self.hold_seat(student=fresh, seat=seat)
        data = client_for(fresh).get("/api/v1/student/dashboard/").json()["data"]
        self.assertEqual(data["pending_hold"]["id"], str(hold.pk))
        self.assertEqual(
            (data["pending_hold"]["seat_label"], data["pending_hold"]["library"]["id"]),
            (seat.label, str(self.library.pk)),
        )
        self.assertIsNotNone(data["pending_hold"]["expires_at"])

    def test_roles(self):
        self.assertEqual(self.owner.get("/api/v1/student/dashboard/").status_code, 403)
        self.assertEqual(APIClient().get("/api/v1/student/dashboard/").status_code, 401)
