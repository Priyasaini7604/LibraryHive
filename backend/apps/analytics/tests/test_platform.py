"""Internal platform analytics: access control and metric correctness (counts, uniqueness, ranges)."""

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics import platform_selectors
from apps.attendance.models import AttendanceRecord
from apps.core.dates import business_today
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.tests.base import make_library, make_plan
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.models import Payment, UpiPaymentRequest
from apps.seats.models import Seat, SeatHold

BASE = "/api/v1/platform/analytics/"
ENDPOINTS = ["overview/", "bookings/", "libraries/", "subscriptions/"]


def make_admin():
    return get_user_model().objects.create_superuser(email="team@example.com", name="Team", password="Str0ng-pass-123")


def client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(get_user_model().objects.get(pk=user.pk))
    return client


def at(day, hour=12):
    return timezone.make_aware(datetime.combine(day, time(hour)))


def book(library, student, *, day=None, source="online", state="active"):
    """One booking (membership) created on `day`."""
    seat = Seat.objects.create(library=library, label=f"S{Seat.objects.count()}")
    extra = {"archived_at": timezone.now(), "archived_by": library.owner} if state == "archived" else {}
    membership = make_membership(
        library=library,
        plan=library.plans.first() or make_plan(library),
        student=student,
        seat=seat,
        source=source,
        state=state,
        **extra,
    )
    if day:
        Membership.objects.filter(pk=membership.pk).update(created_at=at(day))
    return membership


class PlatformAccessTests(TestCase):
    def test_super_admin_can_read_every_endpoint(self):
        client = client_for(make_admin())
        for endpoint in ENDPOINTS:
            response = client.get(BASE + endpoint)
            self.assertEqual(response.status_code, 200, endpoint)
            self.assertTrue(response.json()["success"])

    def test_owner_is_forbidden(self):
        client = client_for(make_library().owner)
        for endpoint in ENDPOINTS:
            self.assertEqual(client.get(BASE + endpoint).status_code, 403, endpoint)

    def test_student_is_forbidden(self):
        client = client_for(make_student())
        for endpoint in ENDPOINTS:
            self.assertEqual(client.get(BASE + endpoint).status_code, 403, endpoint)

    def test_anonymous_is_rejected(self):
        client = client_for(None)
        for endpoint in ENDPOINTS:
            self.assertEqual(client.get(BASE + endpoint).status_code, 401, endpoint)

    def test_staff_without_superuser_is_forbidden(self):
        staff = make_owner(is_staff=True)
        self.assertEqual(client_for(staff).get(BASE + "overview/").status_code, 403)

    def test_inactive_superuser_is_forbidden(self):
        admin = make_admin()
        get_user_model().objects.filter(pk=admin.pk).update(is_active=False)
        self.assertEqual(client_for(admin).get(BASE + "overview/").status_code, 403)

    def test_only_the_admin_gets_the_platform_flag_on_me(self):
        admin, owner = make_admin(), make_owner()
        client = client_for(admin)
        self.assertTrue(client.get("/api/v1/auth/me/").json()["data"]["is_platform_admin"])
        self.assertFalse(client_for(owner).get("/api/v1/auth/me/").json()["data"]["is_platform_admin"])

    def test_responses_contain_no_personal_data(self):
        library = make_library()
        student = make_student(email="secret.student@example.com")
        book(library, student, day=business_today())
        client = client_for(make_admin())
        body = "".join(client.get(BASE + endpoint).content.decode() for endpoint in ENDPOINTS)
        self.assertNotIn("secret.student@example.com", body)
        self.assertNotIn(library.owner.email, body)


class PlatformMetricTests(TestCase):
    def setUp(self):
        self.today = business_today()
        self.lib_a, self.lib_b = make_library(), make_library()
        self.s1, self.s2, self.s3 = make_student(), make_student(), make_student()
        self.admin = client_for(make_admin())

    def data(self, endpoint, **params):
        response = self.admin.get(BASE + endpoint, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]

    def test_one_student_with_many_bookings_is_one_unique_student(self):
        for _ in range(3):
            book(self.lib_a, self.s1, day=self.today, state="archived")
        book(self.lib_a, self.s1, day=self.today)
        book(self.lib_b, self.s2, day=self.today)
        bookings = self.data("overview/")["bookings"]
        self.assertEqual(bookings["total"], 5)
        self.assertEqual(bookings["unique_students"], 2)
        self.assertEqual(bookings["monthly_active_students"], 2)

    def test_students_split_registered_and_offline(self):
        make_student(is_offline=True)
        students = self.data("overview/")["students"]
        self.assertEqual(students["registered"], 3)
        self.assertEqual(students["offline_walk_ins"], 1)

    def test_repeat_booking_percent(self):
        book(self.lib_a, self.s1, day=self.today, state="archived")
        book(self.lib_b, self.s1, day=self.today)
        book(self.lib_a, self.s2, day=self.today)
        data = self.data("bookings/")["in_range"]
        self.assertEqual(data["bookings"], 3)
        self.assertEqual(data["unique_students"], 2)
        self.assertEqual(data["repeat_students"], 1)
        self.assertEqual(data["repeat_booking_percent"], 50.0)

    def test_date_range_filters_bookings(self):
        book(self.lib_a, self.s1, day=self.today - timedelta(days=40))
        book(self.lib_a, self.s2, day=self.today - timedelta(days=3))
        book(self.lib_b, self.s3, day=self.today)
        week = self.data(
            "bookings/", **{"from": (self.today - timedelta(days=7)).isoformat(), "to": self.today.isoformat()}
        )
        self.assertEqual(week["in_range"]["bookings"], 2)
        self.assertEqual(week["in_range"]["unique_students"], 2)
        self.assertEqual(sum(point["bookings"] for point in week["trend"]), 2)
        self.assertEqual(len(week["trend"]), 8)  # zero-filled, both ends inclusive
        everything = self.data(
            "bookings/", **{"from": (self.today - timedelta(days=60)).isoformat(), "to": self.today.isoformat()}
        )
        self.assertEqual(everything["in_range"]["bookings"], 3)

    def test_range_boundaries_are_inclusive_in_business_time(self):
        book(self.lib_a, self.s1, day=self.today - timedelta(days=1))
        Membership.objects.update(created_at=at(self.today - timedelta(days=1), hour=23))
        only_yesterday = self.data(
            "bookings/",
            **{
                "from": (self.today - timedelta(days=1)).isoformat(),
                "to": (self.today - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(only_yesterday["in_range"]["bookings"], 1)
        only_today = self.data("bookings/", **{"from": self.today.isoformat(), "to": self.today.isoformat()})
        self.assertEqual(only_today["in_range"]["bookings"], 0)

    def test_today_week_month_cards(self):
        book(self.lib_a, self.s1, day=self.today)
        book(self.lib_a, self.s2, day=self.today - timedelta(days=45))
        data = self.data("bookings/")
        self.assertEqual(data["today"], 1)
        self.assertGreaterEqual(data["this_month"], 1)
        self.assertEqual(data["this_week"], 1)

    def test_cancelled_and_expired_holds_are_not_bookings(self):
        book(self.lib_a, self.s1, day=self.today)
        seats = [Seat.objects.create(library=self.lib_a, label=f"H{i}") for i in range(3)]
        plan = self.lib_a.plans.first()
        for seat, status in zip(seats, ["cancelled", "expired", "completed"], strict=True):
            SeatHold.objects.create(
                seat=seat, library=self.lib_a, kind="booking", student=self.s2, plan=plan, status=status,
                expires_at=timezone.now() + timedelta(minutes=15), created_by=self.s2,
            )  # fmt: skip
        data = self.data("bookings/")
        self.assertEqual(data["in_range"]["bookings"], 1)  # holds never inflate bookings
        self.assertEqual(data["holds"]["abandoned"], 2)
        self.assertEqual(data["holds"]["completed"], 1)
        self.assertAlmostEqual(data["holds"]["abandoned_percent"], 66.7)

    def test_archived_memberships_still_count_as_bookings_and_are_reported_separately(self):
        book(self.lib_a, self.s1, day=self.today, state="archived")
        data = self.data("bookings/")
        self.assertEqual(data["in_range"]["bookings"], 1)
        self.assertEqual(data["in_range"]["archived_memberships"], 1)

    def test_library_rows_do_not_double_count(self):
        # Many check-ins and several students at one library must not multiply the booking counts.
        first = book(self.lib_a, self.s1, day=self.today)
        book(self.lib_a, self.s2, day=self.today, source="offline")
        book(self.lib_a, self.s1, day=self.today, state="archived")
        book(self.lib_b, self.s3, day=self.today)
        for hour in range(4):
            AttendanceRecord.objects.create(
                student=self.s1,
                library=self.lib_a,
                membership=first,
                seat=first.seat,
                date=self.today - timedelta(days=hour),
                check_in_at=timezone.now() - timedelta(days=hour, hours=2),
                check_out_at=timezone.now() - timedelta(days=hour, hours=1),
                check_in_method="self",
                check_out_method="self",
                status="closed",
            )  # fmt: skip
        page = self.data("libraries/")
        rows = {row["id"]: row for row in page["items"]}
        a, b = rows[str(self.lib_a.pk)], rows[str(self.lib_b.pk)]
        self.assertEqual(page["total"], 2)
        self.assertEqual(a["total_bookings"], 3)
        self.assertEqual(a["bookings_in_range"], 3)
        self.assertEqual(a["registered_members"], 2)  # s1 booked twice, s2 once
        self.assertEqual(a["unique_students_in_range"], 2)
        self.assertEqual(a["active_members"], 2)
        self.assertEqual(a["online_students"], 1)  # only s1 booked online
        self.assertEqual(a["check_ins_in_range"], 4)
        self.assertEqual(b["total_bookings"], 1)
        self.assertEqual(b["check_ins_in_range"], 0)
        self.assertIsNone(a["subscription_plan"])
        self.assertEqual(sum(r["bookings_in_range"] for r in page["items"]), 4)

    def test_libraries_table_paginates_searches_and_orders(self):
        for _ in range(5):
            book(self.lib_b, make_student(), day=self.today)
        book(self.lib_a, self.s1, day=self.today)
        first = self.data("libraries/", page_size=1)
        self.assertEqual(first["total"], 2)
        self.assertEqual(len(first["items"]), 1)
        self.assertEqual(first["items"][0]["id"], str(self.lib_b.pk))
        ascending = self.data("libraries/", ordering="bookings", page_size=1)
        self.assertEqual(ascending["items"][0]["id"], str(self.lib_a.pk))
        type(self.lib_a).objects.filter(pk=self.lib_a.pk).update(name="Zebra Reading Room")
        found = self.data("libraries/", search="zebra")
        self.assertEqual([row["id"] for row in found["items"]], [str(self.lib_a.pk)])
        self.assertEqual(self.admin.get(BASE + "libraries/", {"ordering": "owner__email"}).status_code, 400)

    def test_by_library_distribution_sums_to_total(self):
        book(self.lib_a, self.s1, day=self.today)
        book(self.lib_a, self.s2, day=self.today)
        book(self.lib_b, self.s1, day=self.today)
        data = self.data("bookings/")
        self.assertEqual(sum(row["bookings"] for row in data["by_library"]), data["in_range"]["bookings"])

    def test_granularity_week_and_month_zero_fill(self):
        book(self.lib_a, self.s1, day=self.today)
        for granularity in ("week", "month"):
            data = self.data("bookings/", granularity=granularity)
            self.assertEqual(sum(point["bookings"] for point in data["trend"]), 1)

    def test_invalid_range_is_rejected(self):
        bad = self.admin.get(BASE + "bookings/", {"from": "2026-02-10", "to": "2026-02-01"})
        self.assertEqual(bad.status_code, 400)
        too_long = self.admin.get(BASE + "bookings/", {"from": "2024-01-01", "to": "2026-01-01"})
        self.assertEqual(too_long.status_code, 400)

    def test_pending_hold_past_expiry_counts_as_abandoned_not_pending(self):
        seats = [Seat.objects.create(library=self.lib_a, label=f"L{i}") for i in range(2)]
        plan = self.lib_a.plans.first() or make_plan(self.lib_a)
        for seat, student, delta in zip(
            seats, [self.s1, self.s2], [timedelta(minutes=-5), timedelta(minutes=10)], strict=True
        ):
            SeatHold.objects.create(
                seat=seat, library=self.lib_a, kind="booking", student=student, plan=plan, status="pending",
                expires_at=timezone.now() + delta, created_by=student,
            )  # fmt: skip
        holds = self.data("bookings/")["holds"]
        self.assertEqual(holds["abandoned"], 1)  # swept or not, a dead hold is abandoned
        self.assertEqual(holds["still_pending"], 1)

    def _hold(self, student, status, *, expired=True):
        seat = Seat.objects.create(library=self.lib_a, label=f"U{Seat.objects.count()}")
        plan = self.lib_a.plans.first() or make_plan(self.lib_a)
        delta = timedelta(minutes=-30) if expired else timedelta(minutes=10)
        hold = SeatHold.objects.create(
            seat=seat, library=self.lib_a, kind="booking", student=student, plan=plan, status=status,
            expires_at=timezone.now() + delta, created_by=student,
        )  # fmt: skip
        return hold, seat, plan

    def _claim(self, hold, seat, plan, student, status, utr):
        extra = (
            {"reviewed_by": self.lib_a.owner, "reviewed_at": timezone.now(), "review_note": "no credit"}
            if status == "rejected"
            else {}
        )
        return UpiPaymentRequest.objects.create(
            library=self.lib_a, student=student, plan=plan, purpose="new_membership", hold=hold, seat=seat,
            amount=plan.price, utr=utr, status=status, **extra,
        )  # fmt: skip

    def test_a_lapsed_hold_behind_a_pending_upi_claim_is_awaiting_review_not_abandoned(self):
        hold, seat, plan = self._hold(self.s1, "pending")  # lapsed, not yet swept
        self._claim(hold, seat, plan, self.s1, "pending", "UTR000000001")
        holds = self.data("bookings/")["holds"]
        self.assertEqual(holds["abandoned"], 0)
        self.assertEqual(holds["awaiting_upi_review"], 1)
        self.assertEqual(holds["still_pending"], 0)
        self.assertEqual(self.data("bookings/")["in_range"]["bookings"], 0)  # still not a confirmed booking

    def test_rejected_and_cancelled_upi_claims_leave_their_holds_abandoned(self):
        for student, status, utr in ((self.s1, "rejected", "UTR000000002"), (self.s2, "cancelled", "UTR000000003")):
            hold, seat, plan = self._hold(student, "expired")
            self._claim(hold, seat, plan, student, status, utr)
        holds = self.data("bookings/")["holds"]
        self.assertEqual((holds["abandoned"], holds["awaiting_upi_review"]), (2, 0))

    def test_an_expired_hold_whose_claim_was_pending_is_not_abandoned_either(self):
        hold, seat, plan = self._hold(self.s3, "expired")
        self._claim(hold, seat, plan, self.s3, "pending", "UTR000000004")
        holds = self.data("bookings/")["holds"]
        self.assertEqual((holds["abandoned"], holds["expired"], holds["awaiting_upi_review"]), (0, 0, 1))

    def test_upi_direct_payments_never_appear_in_the_gateway_figures_or_as_platform_revenue(self):
        member = book(self.lib_a, self.s1, day=self.today)
        plan = self.lib_a.plans.first()
        Payment.objects.create(
            library=self.lib_a, student=self.s1, membership=member, plan=plan, purpose="new_membership",
            channel="offline", method="upi_direct", status="success", amount=plan.price, period_start=member.start_date,
            period_end=member.next_due_date, verified_via="manual", receipt_number="LH-2026-900001",
            recorded_by=self.lib_a.owner, paid_at=timezone.now(),
        )  # fmt: skip
        data = self.data("subscriptions/")
        online = data["student_payments_online"]
        self.assertEqual((online["successful"], online["amount_successful"]), (0, "0"))  # gateway only
        self.assertFalse(online["is_platform_revenue"])
        self.assertIn("platform_revenue", {item["key"] for item in data["unavailable"]})
        self.assertNotIn("mrr", data)
        # a UPI renewal is still a renewal, and its membership is still one online booking
        bookings = self.data("bookings/")["in_range"]
        self.assertEqual((bookings["bookings"], bookings["online"]), (1, 1))

    def test_subscription_and_revenue_gaps_are_declared_not_invented(self):
        book(self.lib_a, self.s1, day=self.today)
        data = self.data("subscriptions/")
        keys = {item["key"] for item in data["unavailable"]}
        self.assertEqual(keys, {"subscription_plan", "plan_limits", "platform_revenue"})
        self.assertFalse(data["student_payments_online"]["is_platform_revenue"])
        self.assertEqual(data["averages_per_library"]["bookings"], 0.5)  # 1 booking / 2 libraries
        self.assertNotIn("mrr", data)

    def test_empty_platform_has_no_division_errors(self):
        Membership.objects.all().delete()
        data = self.data("bookings/")
        self.assertIsNone(data["in_range"]["repeat_booking_percent"])
        self.assertIsNone(data["holds"]["abandoned_percent"])
        self.assertEqual(platform_selectors.overview()["bookings"]["unique_students"], 0)
