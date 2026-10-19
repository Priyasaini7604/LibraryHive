"""Attendance: check-in and check-out, owner tools, auto-close and archival (SPEC.md 4.9, #62-#70)."""

import threading
from datetime import time, timedelta

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.attendance import services
from apps.attendance.models import AttendanceRecord
from apps.core.dates import business_today
from apps.core.exceptions import AppError
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.payments.tests.base import PaymentTestCase, bookable_library, client_for

CHECK_IN = "/api/v1/student/attendance/check-in/"
CHECK_OUT = "/api/v1/student/attendance/check-out/"


class AttendanceBase(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.owner = client_for(self.library.owner)
        self.me = client_for(self.student)
        self.membership = make_membership(library=self.library, plan=self.plan, student=self.student, seat=self.seat)

    def check_in(self, client=None, library=None):
        return (client or self.me).post(CHECK_IN, {"library_id": str((library or self.library).pk)}, format="json")

    def code(self, response):
        return response.json()["error_code"]


class StudentAttendanceTests(AttendanceBase):
    def test_check_in_creates_an_open_record_with_the_seat_snapshot(self):
        response = self.check_in()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(
            (data["status"], data["seat_label"], data["library"]["id"]), ("open", "A-1", str(self.library.pk))
        )
        record = AttendanceRecord.objects.get()
        self.assertEqual(
            (record.student_id, record.membership_id, record.check_in_method, record.date),
            (self.student.pk, self.membership.pk, "self", business_today()),
        )
        self.assertIsNone(record.check_out_at)

    def test_without_an_active_membership_at_that_library(self):
        stranger = client_for(make_student())
        response = self.check_in(stranger)
        self.assertEqual((response.status_code, self.code(response)), (409, "NO_ACTIVE_MEMBERSHIP"))
        other_library, _, _ = bookable_library()
        self.assertEqual(self.code(self.check_in(library=other_library)), "NO_ACTIVE_MEMBERSHIP")
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        self.assertEqual(self.code(self.check_in()), "NO_ACTIVE_MEMBERSHIP")
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_a_second_check_in_is_refused_and_so_is_one_at_another_library(self):
        self.assertEqual(self.check_in().status_code, 201)
        self.assertEqual(self.code(self.check_in()), "ALREADY_CHECKED_IN")
        other_library, other_plan, other_seats = bookable_library()
        make_membership(library=other_library, plan=other_plan, student=self.student, seat=other_seats[0])
        response = self.check_in(library=other_library)
        self.assertEqual((response.status_code, self.code(response)), (409, "ALREADY_CHECKED_IN"))
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_check_out_closes_the_record_with_a_duration(self):
        self.check_in()
        AttendanceRecord.objects.update(check_in_at=timezone.now() - timedelta(minutes=95))
        response = self.me.post(CHECK_OUT)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual((data["status"], data["check_out_method"]), ("closed", "self"))
        self.assertIn(data["duration_minutes"], (95, 96))
        self.assertEqual(self.me.get("/api/v1/student/attendance/current/").json()["data"], None)
        self.assertEqual(self.check_in().status_code, 201)  # may check in again after checking out

    def test_check_out_without_check_in_is_a_400(self):
        response = self.me.post(CHECK_OUT)
        self.assertEqual((response.status_code, self.code(response)), (400, "NOT_CHECKED_IN"))

    def test_current_and_history_with_summary_and_month_filter(self):
        self.check_in()
        current = self.me.get("/api/v1/student/attendance/current/").json()["data"]
        self.assertEqual(current["status"], "open")
        self.me.post(CHECK_OUT)
        last_month = business_today().replace(day=1) - timedelta(days=1)
        old_in = timezone.now() - timedelta(days=40)
        AttendanceRecord.objects.create(
            student=self.student,
            library=self.library,
            membership=self.membership,
            seat=self.seat,
            date=last_month,
            check_in_at=old_in,
            check_out_at=old_in + timedelta(hours=2),
            duration_minutes=120,
            check_in_method="self",
            check_out_method="self",
            status="closed",
        )
        everything = self.me.get("/api/v1/student/attendance/").json()["data"]
        self.assertEqual(len(everything["items"]), 2)
        month = business_today().strftime("%Y-%m")
        data = self.me.get("/api/v1/student/attendance/", {"month": month}).json()["data"]
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["summary"]["days_present"], 1)
        self.assertEqual(self.me.get("/api/v1/student/attendance/", {"month": "2026-13"}).status_code, 400)

    def test_history_shows_only_my_records_and_roles(self):
        self.check_in()
        other = client_for(make_student())
        self.assertEqual(other.get("/api/v1/student/attendance/").json()["data"]["items"], [])
        self.assertEqual(
            self.owner.post(CHECK_IN, {"library_id": str(self.library.pk)}, format="json").status_code, 403
        )
        self.assertEqual(APIClient().post(CHECK_IN, {}, format="json").status_code, 401)
        self.assertEqual(self.me.post(CHECK_IN, {"library_id": "nope"}, format="json").status_code, 400)


class OwnerAttendanceTests(AttendanceBase):
    def test_live_roster_lists_open_records_of_my_library_only(self):
        self.check_in()
        other_library, other_plan, other_seats = bookable_library()
        other_student = make_student()
        make_membership(library=other_library, plan=other_plan, student=other_student, seat=other_seats[0])
        client_for(other_student).post(CHECK_IN, {"library_id": str(other_library.pk)}, format="json")
        live = self.owner.get("/api/v1/owner/attendance/live/").json()["data"]
        self.assertEqual([row["student"]["id"] for row in live], [str(self.student.pk)])
        self.assertEqual(set(live[0]), {"record_id", "student", "seat_label", "check_in_at"})
        self.me.post(CHECK_OUT)
        self.assertEqual(self.owner.get("/api/v1/owner/attendance/live/").json()["data"], [])

    def test_history_filters(self):
        self.check_in()
        self.me.post(CHECK_OUT)
        today = str(business_today())
        get = lambda **q: self.owner.get("/api/v1/owner/attendance/", q).json()["data"]["items"]  # noqa: E731
        self.assertEqual(len(get(date=today)), 1)
        self.assertEqual(len(get(**{"from": today, "to": today})), 1)
        self.assertEqual(get(date="2020-01-01"), [])
        self.assertEqual(len(get(student_id=str(self.student.pk))), 1)
        self.assertEqual(get(student_id=str(make_student().pk)), [])
        self.assertEqual(get(date=today)[0]["student"]["name"], self.student.name)

    def test_manual_check_in_and_out_are_audited(self):
        response = self.owner.post(
            "/api/v1/owner/attendance/check-in/", {"membership_id": str(self.membership.pk)}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        record = AttendanceRecord.objects.get()
        self.assertEqual(record.check_in_method, "owner")
        again = self.owner.post(
            "/api/v1/owner/attendance/check-in/", {"membership_id": str(self.membership.pk)}, format="json"
        )
        self.assertEqual(self.code(again), "ALREADY_CHECKED_IN")
        out = self.owner.post(f"/api/v1/owner/attendance/{record.pk}/check-out/")
        self.assertEqual(out.status_code, 200)
        record.refresh_from_db()
        self.assertEqual((record.status, record.check_out_method), ("closed", "owner"))
        self.assertEqual(
            self.code(self.owner.post(f"/api/v1/owner/attendance/{record.pk}/check-out/")), "NOT_CHECKED_IN"
        )
        actions = set(AuditLog.objects.filter(entity_id=record.pk).values_list("action", flat=True))
        self.assertEqual(actions, {"attendance.check_in", "attendance.check_out"})

    def test_manual_check_in_of_an_archived_or_foreign_membership(self):
        other_library, other_plan, other_seats = bookable_library()
        theirs = make_membership(library=other_library, plan=other_plan, seat=other_seats[0])
        url = "/api/v1/owner/attendance/check-in/"
        self.assertEqual(self.owner.post(url, {"membership_id": str(theirs.pk)}, format="json").status_code, 404)
        Membership.objects.filter(pk=self.membership.pk).update(state="archived", archived_at=timezone.now())
        self.assertEqual(
            self.code(self.owner.post(url, {"membership_id": str(self.membership.pk)}, format="json")),
            "NO_ACTIVE_MEMBERSHIP",
        )

    def test_corrections_are_validated_and_audited_with_a_diff(self):
        self.check_in()
        self.me.post(CHECK_OUT)
        record = AttendanceRecord.objects.get()
        url = f"/api/v1/owner/attendance/{record.pk}/"
        start = timezone.now() - timedelta(hours=5)
        end = start + timedelta(hours=3)
        response = self.owner.patch(
            url,
            {"check_in_at": start.isoformat(), "check_out_at": end.isoformat(), "reason": "Forgot to tap"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        record.refresh_from_db()
        self.assertEqual(record.duration_minutes, 180)
        entry = AuditLog.objects.get(action="attendance.correct", entity_id=record.pk)
        self.assertEqual(entry.reason, "Forgot to tap")
        self.assertIn("before", entry.changes)
        bad = [
            {"check_out_at": (start - timedelta(hours=1)).isoformat(), "reason": "abc"},
            {"check_in_at": (timezone.now() + timedelta(hours=1)).isoformat(), "reason": "abc"},
            {"reason": "abc"},
            {"check_out_at": end.isoformat()},
        ]
        for payload in bad:
            self.assertEqual(self.owner.patch(url, payload, format="json").status_code, 400)

    def test_correcting_an_open_record_with_a_check_out_closes_it(self):
        self.check_in()
        record = AttendanceRecord.objects.get()
        out = timezone.now() - timedelta(minutes=1)
        AttendanceRecord.objects.update(check_in_at=timezone.now() - timedelta(hours=2))
        response = self.owner.patch(
            f"/api/v1/owner/attendance/{record.pk}/",
            {"check_out_at": out.isoformat(), "reason": "Left early"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        record.refresh_from_db()
        self.assertEqual(record.status, "closed")

    def test_isolation_and_roles(self):
        self.check_in()
        record = AttendanceRecord.objects.get()
        stranger_owner = client_for(bookable_library()[0].owner)
        self.assertEqual(stranger_owner.post(f"/api/v1/owner/attendance/{record.pk}/check-out/").status_code, 404)
        self.assertEqual(
            stranger_owner.patch(
                f"/api/v1/owner/attendance/{record.pk}/",
                {"check_in_at": timezone.now().isoformat(), "reason": "abc"},
                format="json",
            ).status_code,
            404,
        )
        self.assertEqual(stranger_owner.get("/api/v1/owner/attendance/").json()["data"]["items"], [])
        self.assertEqual(self.me.get("/api/v1/owner/attendance/live/").status_code, 403)
        self.assertEqual(client_for(make_owner()).get("/api/v1/owner/attendance/live/").status_code, 409)


class AutoCloseAndArchiveTests(AttendanceBase):
    def open_record(self):
        self.check_in()
        return AttendanceRecord.objects.get()

    def test_closes_records_after_the_library_closing_time(self):
        type(self.library).objects.filter(pk=self.library.pk).update(closes_at=time(22, 0))
        record = self.open_record()
        closing = services.closing_time(AttendanceRecord.objects.select_related("library").get(pk=record.pk))
        record.refresh_from_db()
        self.assertEqual(
            services.auto_close_open_records(now=closing - timedelta(minutes=1)), {"checked": 1, "closed": 0}
        )
        self.assertEqual(
            services.auto_close_open_records(now=closing + timedelta(minutes=1)), {"checked": 1, "closed": 1}
        )
        record.refresh_from_db()
        self.assertEqual((record.status, record.check_out_method), ("auto_closed", "auto"))
        self.assertEqual(record.check_out_at, max(closing, record.check_in_at + timedelta(seconds=1)))
        # Running it again changes nothing.
        self.assertEqual(
            services.auto_close_open_records(now=closing + timedelta(hours=1)), {"checked": 0, "closed": 0}
        )

    def test_without_closing_time_the_day_ends_at_23_59(self):
        type(self.library).objects.filter(pk=self.library.pk).update(closes_at=None)
        record = self.open_record()
        record = AttendanceRecord.objects.select_related("library").get(pk=record.pk)
        self.assertEqual(timezone.localtime(services.closing_time(record)).time(), time(23, 59))

    def test_archiving_the_membership_closes_the_open_record(self):
        record = self.open_record()
        response = self.owner.post(
            f"/api/v1/owner/members/{self.membership.pk}/archive/", {"reason": "Left the city"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        record.refresh_from_db()
        self.assertEqual((record.status, record.check_out_method), ("closed", "owner"))
        self.assertTrue(AuditLog.objects.filter(action="attendance.check_out", entity_id=record.pk).exists())

    def test_archiving_a_member_who_is_not_checked_in_is_unaffected(self):
        response = self.owner.post(
            f"/api/v1/owner/members/{self.membership.pk}/archive/", {"reason": "Left the city"}, format="json"
        )
        self.assertEqual(response.status_code, 200)


class DoubleTapRaceTests(TransactionTestCase):
    def test_parallel_check_ins_leave_exactly_one_open_record(self):
        library, plan, seats = bookable_library(domain_codes=[], amenity_codes=[])
        student = make_student()
        make_membership(library=library, plan=plan, student=student, seat=seats[0])
        outcomes: list[str] = []
        barrier = threading.Barrier(4)

        def tap():
            try:
                barrier.wait(timeout=15)
                services.check_in(student=student, library_id=library.pk)
                outcomes.append("ok")
            except AppError as exc:
                outcomes.append(exc.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=tap) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(sorted(outcomes), ["ALREADY_CHECKED_IN"] * 3 + ["ok"])
        self.assertEqual(AttendanceRecord.objects.filter(student=student, check_out_at__isnull=True).count(), 1)
