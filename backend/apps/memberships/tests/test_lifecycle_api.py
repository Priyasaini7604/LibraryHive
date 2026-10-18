"""Archival (#52), dues (#49), the member directory and detail (#50, #51) and the student's views (#56, #57)."""

from datetime import timedelta

from django.utils import timezone

from apps.core.dates import business_today
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.models import Payment
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for


def shift(membership, *, due_in):
    """Move a membership's due date, keeping `start_date` before it (a database rule)."""
    due = business_today() + timedelta(days=due_in)
    Membership.objects.filter(pk=membership.pk).update(start_date=due - timedelta(days=30), next_due_date=due)


class LifecycleBase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.membership = make_membership(
            library=self.library, plan=self.plan, student=self.student, seat=self.seat, due_in=20
        )

    def add_member(self, seat_index, *, due_in, **kwargs):
        seat = self.seats[seat_index] if seat_index < len(self.seats) else None
        member = make_membership(library=self.library, plan=self.plan, seat=seat, **kwargs)
        shift(member, due_in=due_in)
        return member

    def items(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["items"]


class ArchiveTests(LifecycleBase):
    def archive(self, membership=None, reason="Left the city", client=None):
        url = f"/api/v1/owner/members/{(membership or self.membership).pk}/archive/"
        return (client or self.owner).post(url, {"reason": reason}, format="json")

    def test_archiving_frees_the_seat_and_keeps_the_history(self):
        Payment.objects.create(
            library=self.library,
            student=self.student,
            membership=self.membership,
            plan=self.plan,
            purpose="renewal",
            channel="offline",
            method="cash",
            status="success",
            amount="1200.00",
            recorded_by=self.library.owner,
            receipt_number="LH-2026-999999",
            paid_at=timezone.now(),
            period_start=business_today(),
            period_end=business_today() + timedelta(days=30),
        )
        response = self.archive()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["status"], "archived")
        self.membership.refresh_from_db()
        self.assertEqual(
            (
                self.membership.state,
                self.membership.seat_id,
                self.membership.archived_by_id,
                self.membership.archive_reason,
            ),
            ("archived", self.seat.pk, self.library.owner.pk, "Left the city"),
        )
        self.assertIsNotNone(self.membership.archived_at)
        self.assertEqual(Payment.objects.count(), 1)  # the ledger is untouched
        self.assertTrue(AuditLog.objects.filter(action="membership.archive", entity_id=self.membership.pk).exists())
        # The seat is free at once: another student can hold it.
        self.assertEqual(self.hold_seat(student=make_student()).status, "pending")

    def test_archived_twice_is_a_conflict(self):
        self.archive()
        response = self.archive()
        self.assertEqual((response.status_code, response.json()["error_code"]), (409, "MEMBERSHIP_ARCHIVED"))

    def test_a_returning_student_gets_a_new_row(self):
        self.archive()
        again = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)
        self.assertNotEqual(again.pk, self.membership.pk)
        self.assertEqual(Membership.objects.filter(student=self.student).count(), 2)

    def test_reason_roles_and_isolation(self):
        self.assertEqual(self.archive(reason="ab").status_code, 400)
        self.assertEqual(self.archive(client=client_for(self.student)).status_code, 403)
        other_owner_client = client_for(bookable_library()[0].owner)
        self.assertEqual(self.archive(client=other_owner_client).status_code, 404)
        self.assertEqual(
            client_for(make_owner())
            .post(f"/api/v1/owner/members/{self.membership.pk}/archive/", {"reason": "abc"}, format="json")
            .status_code,
            409,
        )
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.state, "active")


class DuesTests(LifecycleBase):
    def test_lists_due_and_overdue_most_overdue_first_with_amounts(self):
        shift(self.membership, due_in=40)  # not due
        due_soon = self.add_member(1, due_in=2)
        late_3 = self.add_member(2, due_in=-3)
        rows = self.items(self.owner.get("/api/v1/owner/dues/"))
        self.assertEqual([r["membership_id"] for r in rows], [str(late_3.pk), str(due_soon.pk)])
        self.assertEqual((rows[0]["status"], rows[0]["days_overdue"], rows[0]["amount_due"]), ("overdue", 3, "1200.00"))
        self.assertEqual(rows[0]["plan"]["id"], str(self.plan.pk))  # lets the UI renew without changing the plan
        self.assertEqual((rows[1]["status"], rows[1]["days_overdue"]), ("due", 0))
        self.assertEqual(
            set(rows[0]),
            {
                "membership_id",
                "student",
                "seat_label",
                "plan",
                "status",
                "next_due_date",
                "days_overdue",
                "amount_due",
            },
        )

    def test_amount_due_multiplies_by_the_periods_overdue(self):
        late = self.add_member(1, due_in=-65)  # 65 days over a 30-day plan: 3 periods
        rows = self.items(self.owner.get("/api/v1/owner/dues/"))
        row = next(r for r in rows if r["membership_id"] == str(late.pk))
        self.assertEqual((row["days_overdue"], row["amount_due"]), (65, "3600.00"))

    def test_status_and_bucket_filters(self):
        self.add_member(1, due_in=2)
        a = self.add_member(2, due_in=-3)
        b = self.add_member(3, due_in=-10)
        ids = lambda **q: {r["membership_id"] for r in self.items(self.owner.get("/api/v1/owner/dues/", q))}  # noqa: E731
        self.assertEqual(len(ids(status="overdue")), 2)
        self.assertEqual(len(ids(status="due")), 1)
        self.assertEqual(ids(bucket="1-7"), {str(a.pk)})
        self.assertEqual(ids(bucket="8-15"), {str(b.pk)})
        self.assertEqual(ids(bucket="15+"), set())
        self.assertEqual(self.owner.get("/api/v1/owner/dues/", {"bucket": "zzz"}).status_code, 400)

    def test_archived_members_never_appear_and_other_libraries_are_isolated(self):
        gone = self.add_member(1, due_in=-5)
        Membership.objects.filter(pk=gone.pk).update(state="archived", archived_at=timezone.now())
        other_library, other_plan, other_seats = bookable_library()
        late = make_membership(library=other_library, plan=other_plan, seat=other_seats[0])
        shift(late, due_in=-4)
        self.assertEqual(self.items(self.owner.get("/api/v1/owner/dues/")), [])

    def test_roles(self):
        self.assertEqual(client_for(self.student).get("/api/v1/owner/dues/").status_code, 403)


class DirectoryTests(LifecycleBase):
    def test_default_is_everyone_not_archived_with_the_documented_row(self):
        gone = self.add_member(1, due_in=5)
        Membership.objects.filter(pk=gone.pk).update(state="archived", archived_at=timezone.now())
        rows = self.items(self.owner.get("/api/v1/owner/members/"))
        self.assertEqual([r["membership_id"] for r in rows], [str(self.membership.pk)])
        row = rows[0]
        self.assertEqual(
            set(row), {"membership_id", "student", "seat", "plan", "source", "status", "start_date", "next_due_date"}
        )
        self.assertEqual(row["student"]["id"], str(self.student.pk))
        self.assertEqual((row["status"], row["source"], row["seat"]["label"]), ("active", "online", "A-1"))

    def test_filters(self):
        due = self.add_member(1, due_in=2, source="offline")
        gone = self.add_member(2, due_in=5)
        Membership.objects.filter(pk=gone.pk).update(state="archived", archived_at=timezone.now())
        get = lambda **q: {r["membership_id"] for r in self.items(self.owner.get("/api/v1/owner/members/", q))}  # noqa: E731
        self.assertEqual(get(status="due"), {str(due.pk)})
        self.assertEqual(get(status="active"), {str(self.membership.pk)})
        self.assertEqual(get(status="archived"), {str(gone.pk)})
        self.assertEqual(get(source="offline"), {str(due.pk)})
        type(self.student).objects.filter(pk=self.student.pk).update(
            name="Zorro Quillfeather"
        )  # unique, so a search can't match others
        self.assertEqual(get(search="Quillfeather"), {str(self.membership.pk)})
        self.assertEqual(get(search="A-2"), {str(due.pk)})  # the "2" is not treated as a phone number
        self.assertEqual(get(search="+91 " + self.student.phone.removeprefix("+91")), {str(self.membership.pk)})
        self.assertEqual(get(search=self.student.phone), {str(self.membership.pk)})
        self.assertEqual(self.owner.get("/api/v1/owner/members/", {"status": "bogus"}).status_code, 400)

    def test_other_libraries_members_are_invisible(self):
        other_library, other_plan, other_seats = bookable_library()
        theirs = make_membership(library=other_library, plan=other_plan, seat=other_seats[0])
        rows = self.items(self.owner.get("/api/v1/owner/members/"))
        self.assertNotIn(str(theirs.pk), {r["membership_id"] for r in rows})
        self.assertEqual(self.owner.get(f"/api/v1/owner/members/{theirs.pk}/").status_code, 404)

    def test_detail_has_period_history_and_other_tenures(self):
        old = make_membership(
            library=self.library,
            plan=self.plan,
            student=self.student,
            seat=self.seats[1],
            state="archived",
            archived_at=timezone.now(),
        )
        Payment.objects.create(
            library=self.library,
            student=self.student,
            membership=self.membership,
            plan=self.plan,
            purpose="new_membership",
            channel="offline",
            method="cash",
            status="success",
            amount="1200.00",
            recorded_by=self.library.owner,
            receipt_number="LH-2026-999998",
            paid_at=timezone.now(),
            period_start=business_today(),
            period_end=business_today() + timedelta(days=30),
        )
        data = self.owner.get(f"/api/v1/owner/members/{self.membership.pk}/").json()["data"]
        self.assertEqual([p["receipt_number"] for p in data["payments"]], ["LH-2026-999998"])
        self.assertEqual([m["membership_id"] for m in data["other_memberships_here"]], [str(old.pk)])
        self.assertEqual(data["other_memberships_here"][0]["status"], "archived")
        self.assertNotIn("gateway_order_id", str(data))
        self.assertEqual(data["complaints_count"], 0)
        self.assertEqual(data["attendance_summary"], {"this_month_days": 0, "last_check_in": None})

    def test_detail_counts_this_members_attendance_and_complaints_only(self):
        from apps.attendance.models import AttendanceRecord
        from apps.complaints.models import Complaint

        other = make_membership(library=self.library, plan=self.plan, seat=self.seats[1])
        now = timezone.now()
        for member, days in ((self.membership, 2), (other, 5)):
            for offset in range(days):
                AttendanceRecord.objects.create(
                    student=member.student,
                    library=self.library,
                    membership=member,
                    seat=member.seat,
                    date=business_today(),
                    check_in_at=now - timedelta(hours=offset + 2),
                    check_out_at=now - timedelta(hours=offset + 1),
                    duration_minutes=60,
                    check_in_method="self",
                    check_out_method="self",
                    status="closed",
                )
        Complaint.objects.create(
            student=self.student, library=self.library, membership=self.membership, category="ac", description="x" * 12
        )
        data = self.owner.get(f"/api/v1/owner/members/{self.membership.pk}/").json()["data"]
        self.assertEqual(data["complaints_count"], 1)
        self.assertEqual(data["attendance_summary"]["this_month_days"], 1)  # the same business date counts once
        self.assertIsNotNone(data["attendance_summary"]["last_check_in"])

    def test_roles(self):
        self.assertEqual(client_for(self.student).get("/api/v1/owner/members/").status_code, 403)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/members/").status_code, 409)


class StudentMembershipTests(LifecycleBase):
    def test_lists_own_memberships_with_renewal_flag_and_days_to_due(self):
        shift(self.membership, due_in=5)
        response = client_for(self.student).get("/api/v1/student/memberships/")
        self.assertEqual(response.status_code, 200)
        row = response.json()["data"][0]
        self.assertEqual(
            (row["id"], row["status"], row["days_to_due"], row["renewal_open"]),
            (str(self.membership.pk), "active", 5, True),
        )
        self.assertEqual(
            row["plan"], {"id": str(self.plan.pk), "name": "Monthly", "price": "1200.00", "duration_days": 30}
        )
        self.assertEqual((row["library"]["id"], row["seat"]), (str(self.library.pk), {"label": "A-1"}))

    def test_renewal_is_closed_when_the_due_date_is_far(self):
        shift(self.membership, due_in=20)
        row = client_for(self.student).get("/api/v1/student/memberships/").json()["data"][0]
        self.assertFalse(row["renewal_open"])

    def test_archived_ones_only_on_request_and_never_other_students(self):
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        stranger = make_membership(library=self.library, plan=self.plan, seat=self.seats[1])
        client = client_for(self.student)
        self.assertEqual(client.get("/api/v1/student/memberships/").json()["data"], [])
        data = client.get("/api/v1/student/memberships/", {"include_archived": "true"}).json()["data"]
        self.assertEqual([r["id"] for r in data], [str(self.membership.pk)])
        self.assertEqual(client.get(f"/api/v1/student/memberships/{stranger.pk}/").status_code, 404)

    def test_detail_includes_payment_periods(self):
        Payment.objects.create(
            library=self.library,
            student=self.student,
            membership=self.membership,
            plan=self.plan,
            purpose="new_membership",
            channel="offline",
            method="upi_direct",
            status="success",
            amount="1200.00",
            recorded_by=self.library.owner,
            receipt_number="LH-2026-999997",
            paid_at=timezone.now(),
            period_start=business_today(),
            period_end=business_today() + timedelta(days=30),
        )
        data = client_for(self.student).get(f"/api/v1/student/memberships/{self.membership.pk}/").json()["data"]
        self.assertEqual(data["payments"][0]["receipt_number"], "LH-2026-999997")
        self.assertEqual(data["payments"][0]["method"], "upi_direct")

    def test_roles(self):
        self.assertEqual(self.owner.get("/api/v1/student/memberships/").status_code, 403)
