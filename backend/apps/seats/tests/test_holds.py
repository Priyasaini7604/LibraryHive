"""Seat holds (T12): booking holds #38-#40, manual holds #36, release #37, expiry (BOOK-01..05, SEAT-07)."""

import threading
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import AppError, lookup_constraint_error
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.models import Library
from apps.libraries.tests.base import make_library, make_plan
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import make_membership
from apps.seats import selectors, services
from apps.seats.models import Seat, SeatHold

HOLDS = "/api/v1/student/holds/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(type(user).objects.get(pk=user.pk))
    return client


def bookable_library(*, seats=3, **kwargs):
    """A published library: plan plus real seats (the publish rule counts them)."""
    library = make_library(**kwargs)
    plan = make_plan(library)
    services.create_seats(library=library, actor=library.owner, specs=services.grid_specs(["A"], seats))
    library.refresh_from_db()
    return library, plan, list(Seat.objects.filter(library=library).order_by("position"))


class HoldTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.library, self.plan, self.seats = bookable_library()
        self.seat = self.seats[0]
        self.student = make_student()
        self.owner = client_for(self.library.owner)

    def hold_as(self, student, seat=None, plan=None, **extra):
        return client_for(student).post(
            HOLDS,
            {"seat_id": str((seat or self.seat).pk), "plan_id": str((plan or self.plan).pk), **extra},
            format="json",
        )

    def make_hold(self, student=None, seat=None, **overrides):
        values = {
            "seat": seat or self.seat,
            "library": self.library,
            "kind": SeatHold.Kind.BOOKING,
            "student": student or self.student,
            "plan": self.plan,
            "created_by": student or self.student,
            "expires_at": timezone.now() + timedelta(minutes=15),
            **overrides,
        }
        return SeatHold.objects.create(**values)

    def error_code(self, response):
        return response.json()["error_code"]


class CreateBookingHoldTests(HoldTestCase):
    def test_creates_a_hold_with_the_documented_response(self):
        before = timezone.now()
        response = self.hold_as(self.student)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(set(data), {"id", "seat", "library", "plan", "amount", "expires_at"})
        self.assertEqual(data["seat"], {"id": str(self.seat.pk), "label": "A-1"})
        self.assertEqual(data["library"], {"id": str(self.library.pk), "name": self.library.name})
        self.assertEqual(data["plan"]["price"], "1200.00")
        self.assertEqual(data["amount"], "1200.00")
        hold = SeatHold.objects.get()
        self.assertEqual(
            (hold.kind, hold.status, hold.library_id, hold.created_by_id),
            ("booking", "pending", self.library.pk, self.student.pk),
        )
        self.assertLess(abs((hold.expires_at - before) - timedelta(minutes=15)), timedelta(seconds=30))
        row = AuditLog.objects.get(action="hold.create")
        self.assertEqual((row.library_id, row.actor_id, row.entity_id), (self.library.pk, self.student.pk, hold.pk))

    @override_settings(SEAT_HOLD_MINUTES=5)
    def test_hold_window_is_configurable(self):
        self.hold_as(self.student)
        hold = SeatHold.objects.get()
        self.assertLess(hold.expires_at - timezone.now(), timedelta(minutes=5, seconds=5))

    def test_client_cannot_choose_amount_status_or_expiry(self):
        response = self.hold_as(
            self.student, amount="1.00", status="completed", expires_at="2099-01-01T00:00:00Z", kind="owner_manual"
        )
        self.assertEqual(response.status_code, 201)
        hold = SeatHold.objects.get()
        self.assertEqual((hold.kind, hold.status), ("booking", "pending"))
        self.assertEqual(response.json()["data"]["amount"], "1200.00")
        self.assertLess(hold.expires_at, timezone.now() + timedelta(hours=1))

    def test_validation_and_unknown_ids(self):
        client = client_for(self.student)
        for payload in ({}, {"seat_id": "x", "plan_id": str(self.plan.pk)}, {"seat_id": str(self.seat.pk)}):
            self.assertEqual(client.post(HOLDS, payload, format="json").status_code, 400, payload)
        import uuid

        missing = client.post(HOLDS, {"seat_id": str(uuid.uuid4()), "plan_id": str(self.plan.pk)}, format="json")
        self.assertEqual((missing.status_code, self.error_code(missing)), (404, "NOT_FOUND"))

    def test_removed_seat_is_not_found(self):
        Seat.objects.filter(pk=self.seat.pk).update(is_active=False)
        self.assertEqual(self.hold_as(self.student).status_code, 404)

    def test_unpublished_or_inactive_library_is_not_bookable(self):
        Library.objects.filter(pk=self.library.pk).update(is_published=False)
        self.assertEqual(self.error_code(self.hold_as(self.student)), "LIBRARY_NOT_BOOKABLE")
        Library.objects.filter(pk=self.library.pk).update(is_published=True, is_active=False)
        self.assertEqual(self.error_code(self.hold_as(self.student)), "LIBRARY_NOT_BOOKABLE")
        self.assertFalse(SeatHold.objects.exists())

    def test_inactive_plan_or_another_librarys_plan_is_rejected(self):
        _, other_plan, _ = bookable_library(name="Other Library")
        for plan in (other_plan,):
            response = self.hold_as(self.student, plan=plan)
            self.assertEqual((response.status_code, self.error_code(response)), (409, "PLAN_INACTIVE"))
        type(self.plan).objects.filter(pk=self.plan.pk).update(is_active=False)
        self.assertEqual(self.error_code(self.hold_as(self.student)), "PLAN_INACTIVE")
        self.assertFalse(SeatHold.objects.exists())

    def test_disabled_seat_is_unavailable(self):
        Seat.objects.filter(pk=self.seat.pk).update(is_disabled=True, disabled_reason="Broken")
        response = self.hold_as(self.student)
        self.assertEqual((response.status_code, self.error_code(response)), (409, "SEAT_UNAVAILABLE"))

    def test_occupied_seat_is_unavailable_even_when_the_member_is_overdue(self):
        make_membership(
            library=self.library,
            plan=self.plan,
            seat=self.seat,
            student=make_student(),
            due_in=-5,
            start_date=timezone.now().date() - timedelta(days=60),
        )
        response = self.hold_as(self.student)
        self.assertEqual((response.status_code, self.error_code(response)), (409, "SEAT_UNAVAILABLE"))

    def test_an_archived_member_frees_the_seat(self):
        make_membership(
            library=self.library,
            plan=self.plan,
            seat=self.seat,
            student=make_student(),
            state=Membership.State.ARCHIVED,
            archived_at=timezone.now(),
        )
        self.assertEqual(self.hold_as(self.student).status_code, 201)

    def test_existing_member_of_the_library_cannot_book_another_seat(self):
        make_membership(library=self.library, plan=self.plan, seat=self.seats[1], student=self.student)
        response = self.hold_as(self.student)
        self.assertEqual((response.status_code, self.error_code(response)), (409, "ALREADY_MEMBER"))

    def test_seat_held_by_another_student_is_unavailable(self):
        self.assertEqual(self.hold_as(self.student).status_code, 201)
        response = self.hold_as(make_student())
        self.assertEqual((response.status_code, self.error_code(response)), (409, "SEAT_UNAVAILABLE"))
        self.assertEqual(SeatHold.objects.count(), 1)

    def test_second_hold_in_the_same_library_is_hold_exists(self):
        self.assertEqual(self.hold_as(self.student).status_code, 201)
        response = self.hold_as(self.student, seat=self.seats[1])
        self.assertEqual((response.status_code, self.error_code(response)), (409, "HOLD_EXISTS"))

    def test_holds_in_different_libraries_are_independent(self):
        _, other_plan, other_seats = bookable_library(name="Other Library")
        self.assertEqual(self.hold_as(self.student).status_code, 201)
        self.assertEqual(self.hold_as(self.student, seat=other_seats[0], plan=other_plan).status_code, 201)

    def test_manual_hold_blocks_booking(self):
        services.place_manual_hold(
            library=self.library, seat_id=self.seat.pk, actor=self.library.owner, reason="Reserved"
        )
        response = self.hold_as(self.student)
        self.assertEqual((response.status_code, self.error_code(response)), (409, "SEAT_UNAVAILABLE"))

    def test_a_dead_hold_is_free_immediately_without_the_cleanup_job(self):
        old = self.make_hold(student=make_student(), expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(old.status, "pending")  # the job has not run
        self.assertFalse(selectors.live_hold_exists(self.seat))
        response = self.hold_as(self.student)
        self.assertEqual(response.status_code, 201)
        old.refresh_from_db()
        self.assertEqual((old.status, old.closed_at is not None), ("expired", True))

    def test_own_expired_hold_does_not_block_a_new_one(self):
        self.make_hold(expires_at=timezone.now() - timedelta(minutes=1))
        response = self.hold_as(self.student, seat=self.seats[1])
        self.assertEqual(response.status_code, 201)

    def test_only_students_can_hold_and_anonymous_is_rejected(self):
        payload = {"seat_id": str(self.seat.pk), "plan_id": str(self.plan.pk)}
        self.assertEqual(APIClient().post(HOLDS, payload, format="json").status_code, 401)
        self.assertEqual(client_for(self.library.owner).post(HOLDS, payload, format="json").status_code, 403)

    def test_hold_creation_is_throttled(self):
        from django.conf import settings

        rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "hold_create": "2/min"}
        with mock.patch("rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES", rates):
            statuses = [self.hold_as(self.student, seat=seat).status_code for seat in self.seats]
        self.assertEqual(statuses, [201, 409, 429])  # the second is HOLD_EXISTS but still counts


class ConstraintTests(HoldTestCase):
    def test_database_allows_one_pending_hold_per_seat(self):
        self.make_hold()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_hold(student=make_student())

    def test_closed_holds_do_not_block_the_seat(self):
        self.make_hold(status="cancelled", closed_at=timezone.now())
        self.make_hold(status="expired", closed_at=timezone.now(), student=make_student())
        self.make_hold(student=make_student())

    def test_database_allows_one_pending_booking_hold_per_student_and_library(self):
        self.make_hold()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_hold(seat=self.seats[1])

    def test_booking_hold_needs_student_plan_and_expiry(self):
        complete = {
            "seat": self.seat,
            "library": self.library,
            "kind": "booking",
            "student": self.student,
            "plan": self.plan,
            "created_by": self.student,
            "expires_at": timezone.now(),
        }
        for missing in ("student", "plan", "expires_at"):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SeatHold.objects.create(**{**complete, missing: None})

    def test_manual_hold_needs_a_reason_and_no_expiry(self):
        base = {"kind": "owner_manual", "student": None, "plan": None, "created_by": self.library.owner}
        for overrides in ({"reason": "", "expires_at": None}, {"reason": "Why", "expires_at": timezone.now()}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.make_hold(**{**base, **overrides})
        self.make_hold(**{**base, "reason": "Reserved", "expires_at": None})

    def test_lost_races_map_to_clean_conflicts(self):
        self.assertEqual(lookup_constraint_error("seathold_one_pending_per_seat")[1], "SEAT_UNAVAILABLE")
        self.assertEqual(lookup_constraint_error("seathold_one_pending_per_student_library")[1], "HOLD_EXISTS")

    def test_live_queryset_follows_the_liveness_rule(self):
        booking = self.make_hold()
        manual = SeatHold.objects.create(
            seat=self.seats[1],
            library=self.library,
            kind="owner_manual",
            reason="Reserved",
            created_by=self.library.owner,
        )
        dead = self.make_hold(
            student=make_student(), seat=self.seats[2], expires_at=timezone.now() - timedelta(seconds=1)
        )
        done = self.make_hold(student=make_student(), seat=self.seats[2], status="completed", closed_at=timezone.now())
        live = set(SeatHold.objects.live().values_list("pk", flat=True))
        self.assertEqual(live, {booking.pk, manual.pk})
        self.assertNotIn(dead.pk, live)
        self.assertNotIn(done.pk, live)


class CurrentAndCancelTests(HoldTestCase):
    def test_current_lists_only_my_live_booking_holds(self):
        mine = self.make_hold()
        self.make_hold(student=make_student(), seat=self.seats[1])
        self.make_hold(student=self.student, seat=self.seats[2], status="cancelled", closed_at=timezone.now())
        data = client_for(self.student).get(HOLDS + "current/").json()["data"]
        self.assertEqual([h["id"] for h in data], [str(mine.pk)])
        self.assertEqual(set(data[0]), {"id", "seat", "library", "plan", "amount", "expires_at"})

    def test_expired_hold_is_not_current_even_before_cleanup(self):
        self.make_hold(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(client_for(self.student).get(HOLDS + "current/").json()["data"], [])

    def test_current_requires_a_student(self):
        self.assertEqual(APIClient().get(HOLDS + "current/").status_code, 401)
        self.assertEqual(self.owner.get(HOLDS + "current/").status_code, 403)

    def test_cancel_frees_the_seat_at_once(self):
        hold = self.make_hold()
        response = client_for(self.student).post(f"{HOLDS}{hold.pk}/cancel/")
        self.assertEqual(response.status_code, 200, response.content)
        hold.refresh_from_db()
        self.assertEqual((hold.status, hold.closed_at is not None), ("cancelled", True))
        self.assertEqual(self.hold_as(make_student()).status_code, 201)
        self.assertTrue(AuditLog.objects.filter(action="hold.cancel", entity_id=hold.pk).exists())

    def test_cancelling_twice_or_after_expiry_is_hold_expired(self):
        hold = self.make_hold()
        client = client_for(self.student)
        client.post(f"{HOLDS}{hold.pk}/cancel/")
        again = client.post(f"{HOLDS}{hold.pk}/cancel/")
        self.assertEqual((again.status_code, self.error_code(again)), (409, "HOLD_EXPIRED"))
        late = self.make_hold(seat=self.seats[1], expires_at=timezone.now() - timedelta(seconds=1))
        response = client.post(f"{HOLDS}{late.pk}/cancel/")
        self.assertEqual((response.status_code, self.error_code(response)), (409, "HOLD_EXPIRED"))
        late.refresh_from_db()
        self.assertEqual(late.status, "expired")

    def test_someone_elses_hold_and_manual_holds_are_404(self):
        theirs = self.make_hold(student=make_student())
        manual = SeatHold.objects.create(
            seat=self.seats[1],
            library=self.library,
            kind="owner_manual",
            reason="Reserved",
            created_by=self.library.owner,
        )
        client = client_for(self.student)
        for hold in (theirs, manual):
            self.assertEqual(client.post(f"{HOLDS}{hold.pk}/cancel/").status_code, 404)
            hold.refresh_from_db()
            self.assertEqual(hold.status, "pending")


class ManualHoldTests(HoldTestCase):
    def url(self, seat=None):
        return f"/api/v1/owner/seats/{(seat or self.seat).pk}/manual-hold/"

    def test_owner_blocks_a_free_seat(self):
        response = self.owner.post(self.url(), {"reason": " Walk-in student, pays tomorrow "}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["kind"], data["status"], data["expires_at"]), ("owner_manual", "pending", None))
        self.assertEqual(data["reason"], "Walk-in student, pays tomorrow")
        hold = SeatHold.objects.get()
        self.assertEqual(
            (hold.library_id, hold.created_by_id, hold.student_id), (self.library.pk, self.library.owner_id, None)
        )
        row = AuditLog.objects.get(action="hold.manual_place")
        self.assertEqual((row.library_id, row.reason), (self.library.pk, "Walk-in student, pays tomorrow"))

    def test_seat_must_be_free(self):
        self.owner.post(self.url(), {"reason": "First one"}, format="json")
        second = self.owner.post(self.url(), {"reason": "Second one"}, format="json")
        self.assertEqual((second.status_code, self.error_code(second)), (409, "SEAT_UNAVAILABLE"))
        make_membership(library=self.library, plan=self.plan, seat=self.seats[1], student=self.student)
        occupied = self.owner.post(self.url(self.seats[1]), {"reason": "Nope nope"}, format="json")
        self.assertEqual(self.error_code(occupied), "SEAT_UNAVAILABLE")
        self.make_hold(student=make_student(), seat=self.seats[2])
        held = self.owner.post(self.url(self.seats[2]), {"reason": "Nope nope"}, format="json")
        self.assertEqual(self.error_code(held), "SEAT_UNAVAILABLE")
        Seat.objects.filter(pk=self.seats[0].pk).update(is_disabled=True, disabled_reason="Broken")
        SeatHold.objects.filter(seat=self.seats[0]).update(status="released", closed_at=timezone.now())
        disabled = self.owner.post(self.url(self.seats[0]), {"reason": "Nope nope"}, format="json")
        self.assertEqual(self.error_code(disabled), "SEAT_UNAVAILABLE")

    def test_a_dead_student_hold_does_not_stop_a_manual_hold(self):
        self.make_hold(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.owner.post(self.url(), {"reason": "Reserved"}, format="json").status_code, 201)

    def test_reason_is_required_and_bounded(self):
        for payload in ({}, {"reason": "ab"}, {"reason": "x" * 201}, {"reason": "   "}):
            self.assertEqual(self.owner.post(self.url(), payload, format="json").status_code, 400, payload)

    def test_other_librarys_seat_students_and_anonymous(self):
        _, _, other_seats = bookable_library(name="Other Library")
        self.assertEqual(
            self.owner.post(self.url(other_seats[0]), {"reason": "Mine now"}, format="json").status_code, 404
        )
        self.assertFalse(SeatHold.objects.exists())
        self.assertEqual(
            client_for(self.student).post(self.url(), {"reason": "Reserved"}, format="json").status_code, 403
        )
        self.assertEqual(APIClient().post(self.url(), {"reason": "Reserved"}, format="json").status_code, 401)
        self.assertEqual(
            client_for(make_owner()).post(self.url(), {"reason": "Reserved"}, format="json").status_code, 409
        )


class ReleaseHoldTests(HoldTestCase):
    def url(self, hold):
        return f"/api/v1/owner/holds/{hold.pk}/release/"

    def test_owner_releases_a_stuck_student_hold(self):
        hold = self.make_hold()
        response = self.owner.post(self.url(hold), {"reason": "Student called to cancel"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["status"], "released")
        hold.refresh_from_db()
        self.assertIsNotNone(hold.closed_at)
        self.assertEqual(self.hold_as(make_student()).status_code, 201)  # seat is free again
        row = AuditLog.objects.get(action="hold.release")
        self.assertEqual(
            (row.library_id, row.reason, row.entity_id), (self.library.pk, "Student called to cancel", hold.pk)
        )

    def test_owner_releases_a_manual_hold(self):
        hold = services.place_manual_hold(
            library=self.library, seat_id=self.seat.pk, actor=self.library.owner, reason="Reserved"
        )
        self.assertEqual(
            self.owner.post(self.url(hold), {"reason": "No longer needed"}, format="json").status_code, 200
        )
        hold.refresh_from_db()
        self.assertEqual(hold.status, "released")
        self.assertEqual(hold.reason, "Reserved")  # the placement reason is kept; the release reason is audited

    def test_only_pending_holds_can_be_released(self):
        for status in ("released", "cancelled", "expired"):
            hold = self.make_hold(status=status, closed_at=timezone.now(), student=make_student(), seat=self.seats[1])
            response = self.owner.post(self.url(hold), {"reason": "Cleaning up"}, format="json")
            self.assertEqual((response.status_code, self.error_code(response)), (409, "HOLD_EXPIRED"), status)

    def test_a_completed_hold_and_its_paid_membership_cannot_be_cancelled_by_release(self):
        hold = self.make_hold(status="completed", closed_at=timezone.now())
        membership = make_membership(library=self.library, plan=self.plan, seat=self.seat, student=self.student)
        response = self.owner.post(self.url(hold), {"reason": "Please cancel it"}, format="json")
        self.assertEqual(self.error_code(response), "HOLD_EXPIRED")
        membership.refresh_from_db()
        self.assertEqual(membership.state, Membership.State.ACTIVE)

    def test_a_pending_hold_past_its_expiry_is_closed_as_expired(self):
        hold = self.make_hold(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.owner.post(self.url(hold), {"reason": "Cleaning up"}, format="json")
        self.assertEqual(self.error_code(response), "HOLD_EXPIRED")
        hold.refresh_from_db()
        self.assertEqual(hold.status, "expired")

    def test_reason_is_required(self):
        hold = self.make_hold()
        for payload in ({}, {"reason": "no"}):
            self.assertEqual(self.owner.post(self.url(hold), payload, format="json").status_code, 400)
        hold.refresh_from_db()
        self.assertEqual(hold.status, "pending")

    def test_isolation_and_roles(self):
        other_library, other_plan, other_seats = bookable_library(name="Other Library")
        theirs = SeatHold.objects.create(
            seat=other_seats[0],
            library=other_library,
            kind="booking",
            student=make_student(),
            plan=other_plan,
            created_by=self.student,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        response = self.owner.post(self.url(theirs), {"reason": "Not mine to touch"}, format="json")
        self.assertEqual((response.status_code, self.error_code(response)), (404, "NOT_FOUND"))
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, "pending")
        mine = self.make_hold()
        self.assertEqual(
            client_for(self.student).post(self.url(mine), {"reason": "Student here"}, format="json").status_code, 403
        )
        self.assertEqual(APIClient().post(self.url(mine), {"reason": "Anonymous"}, format="json").status_code, 401)


class ExpireDeadHoldsTests(HoldTestCase):
    def test_expires_only_pending_booking_holds_past_their_time(self):
        now = timezone.now()
        dead = self.make_hold(student=make_student(), expires_at=now - timedelta(seconds=1))
        live = self.make_hold(student=make_student(), seat=self.seats[1])
        manual = SeatHold.objects.create(
            seat=self.seats[2],
            library=self.library,
            kind="owner_manual",
            reason="Reserved",
            created_by=self.library.owner,
        )
        cancelled = self.make_hold(
            student=make_student(), status="cancelled", closed_at=now, expires_at=now - timedelta(hours=1)
        )
        self.assertEqual(services.expire_dead_holds(now=now), 1)
        for hold in (dead, live, manual, cancelled):
            hold.refresh_from_db()
        self.assertEqual(
            [h.status for h in (dead, live, manual, cancelled)], ["expired", "pending", "pending", "cancelled"]
        )
        self.assertIsNotNone(dead.closed_at)

    def test_is_idempotent_and_audits_once(self):
        self.make_hold(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(services.expire_dead_holds(), 1)
        for _ in range(3):
            self.assertEqual(services.expire_dead_holds(), 0)
        rows = AuditLog.objects.filter(action="hold.expired_batch")
        self.assertEqual([r.changes for r in rows], [{"expired": 1}])
        self.assertEqual(rows[0].actor_role, "system")


class ConcurrentBookingTests(TransactionTestCase):
    """BOOK-02: N students racing for one seat give exactly one success and N-1 SEAT_UNAVAILABLE."""

    def race(self, jobs):
        barrier = threading.Barrier(len(jobs))
        outcomes: list[str] = []

        def worker(job):
            try:
                barrier.wait(timeout=15)
                job()
                outcomes.append("ok")
            except AppError as exc:
                outcomes.append(exc.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(job,)) for job in jobs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return sorted(outcomes)

    def setup_library(self, seats=2):
        library = make_library(domain_codes=[], amenity_codes=[])
        plan = make_plan(library)
        services.create_seats(library=library, actor=library.owner, specs=services.grid_specs(["A"], seats))
        return library, plan, list(Seat.objects.filter(library=library).order_by("position"))

    def test_eight_students_one_seat(self):
        _library, plan, seats = self.setup_library()
        students = [make_student() for _ in range(8)]
        jobs = [
            (lambda s=s: services.create_booking_hold(student=s, seat_id=seats[0].pk, plan_id=plan.pk))
            for s in students
        ]
        self.assertEqual(self.race(jobs), ["SEAT_UNAVAILABLE"] * 7 + ["ok"])
        self.assertEqual(SeatHold.objects.filter(status="pending").count(), 1)

    def test_one_student_two_seats_at_once(self):
        _library, plan, seats = self.setup_library()
        student = make_student()
        jobs = [
            (lambda seat=seat: services.create_booking_hold(student=student, seat_id=seat.pk, plan_id=plan.pk))
            for seat in seats
        ]
        self.assertEqual(self.race(jobs), ["HOLD_EXISTS", "ok"])
        self.assertEqual(SeatHold.objects.filter(student=student, status="pending").count(), 1)

    def test_booking_races_a_manual_hold(self):
        library, plan, seats = self.setup_library()
        student = make_student()
        jobs = [
            lambda: services.create_booking_hold(student=student, seat_id=seats[0].pk, plan_id=plan.pk),
            lambda: services.place_manual_hold(
                library=library, seat_id=seats[0].pk, actor=library.owner, reason="Reserved"
            ),
        ]
        self.assertEqual(self.race(jobs), ["SEAT_UNAVAILABLE", "ok"])
        self.assertEqual(SeatHold.objects.filter(seat=seats[0], status="pending").count(), 1)
