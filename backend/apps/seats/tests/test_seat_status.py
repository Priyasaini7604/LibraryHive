"""Derived seat status, counts, public map, deactivate and disable (T10 remainder: #16, #30, #33, #34, SEAT-08)."""

from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.models import Library
from apps.libraries.tests.base import make_library, make_plan
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import TODAY, make_membership
from apps.seats import selectors, services
from apps.seats.models import Seat, SeatHold

OWNER_SEATS = "/api/v1/owner/seats/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(type(user).objects.get(pk=user.pk))
    return client


def bookable_library(*, seats=4, **kwargs):
    library = make_library(**kwargs)
    plan = make_plan(library)
    services.create_seats(library=library, actor=library.owner, specs=services.grid_specs(["A"], seats))
    library.refresh_from_db()
    return library, plan, list(Seat.objects.filter(library=library).order_by("position"))


class StatusTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.library, self.plan, self.seats = bookable_library()
        self.owner = client_for(self.library.owner)
        self.public = APIClient()

    def hold(self, seat, *, student=None, **overrides):
        values = {
            "seat": seat,
            "library": self.library,
            "kind": SeatHold.Kind.BOOKING,
            "student": student or make_student(),
            "plan": self.plan,
            "expires_at": timezone.now() + timedelta(minutes=15),
            **overrides,
        }
        values.setdefault("created_by", values["student"])
        return SeatHold.objects.create(**values)

    def manual(self, seat, reason="Reserved for a walk-in"):
        return SeatHold.objects.create(
            seat=seat, library=self.library, kind="owner_manual", reason=reason, created_by=self.library.owner
        )

    def occupy(self, seat, **overrides):
        return make_membership(library=self.library, plan=self.plan, seat=seat, student=make_student(), **overrides)

    def statuses(self):
        return {s.label: s.status for s in selectors.seat_map(self.library)}

    def error_code(self, response):
        return response.json()["error_code"]


class DerivedStatusTests(StatusTestCase):
    def test_every_seat_is_empty_at_first(self):
        self.assertEqual(set(self.statuses().values()), {"empty"})

    def test_status_order_disabled_then_occupied_then_reserved_then_empty(self):
        a1, a2, a3, _a4 = self.seats
        self.occupy(a1)
        self.hold(a2)
        Seat.objects.filter(pk=a3.pk).update(is_disabled=True, disabled_reason="Broken")
        self.assertEqual(self.statuses(), {"A-1": "occupied", "A-2": "reserved", "A-3": "disabled", "A-4": "empty"})

    def test_disabled_wins_over_everything_else(self):
        self.occupy(self.seats[0])
        Seat.objects.filter(pk=self.seats[0].pk).update(is_disabled=True, disabled_reason="Broken")
        self.assertEqual(self.statuses()["A-1"], "disabled")

    def test_occupied_wins_over_a_live_hold(self):
        # impossible through the services (the seat lock forbids it) but the rule is still defined by SPEC 4.1
        self.occupy(self.seats[0])
        self.hold(self.seats[0])
        self.assertEqual(self.statuses()["A-1"], "occupied")

    def test_an_overdue_member_still_occupies_the_seat(self):
        self.occupy(self.seats[0], due_in=-10, start_date=TODAY - timedelta(days=90))
        self.assertEqual(self.statuses()["A-1"], "occupied")

    def test_archived_member_frees_the_seat(self):
        self.occupy(self.seats[0], state=Membership.State.ARCHIVED, archived_at=timezone.now())
        self.assertEqual(self.statuses()["A-1"], "empty")

    def test_expired_hold_is_empty_without_any_cleanup(self):
        dead = self.hold(self.seats[0], expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(dead.status, "pending")
        self.assertEqual(self.statuses()["A-1"], "empty")

    def test_manual_hold_is_reserved_and_has_no_expiry(self):
        self.manual(self.seats[0])
        self.assertEqual(self.statuses()["A-1"], "reserved")

    def test_closed_holds_do_not_reserve(self):
        for status in ("cancelled", "released", "expired", "completed"):
            self.hold(self.seats[1], status=status, closed_at=timezone.now())
        self.assertEqual(self.statuses()["A-2"], "empty")

    def test_status_is_one_query_for_the_whole_map(self):
        for seat in self.seats[:2]:
            self.occupy(seat)
        with self.assertNumQueries(1):
            list(selectors.seat_map(self.library))

    def test_removed_seats_have_no_status(self):
        Seat.objects.filter(pk=self.seats[0].pk).update(is_active=False)
        mapped = {s.label: s.status for s in selectors.seat_map(self.library, include_inactive=True)}
        self.assertIsNone(mapped["A-1"])
        self.assertNotIn("A-1", self.statuses())


class CountsTests(StatusTestCase):
    def test_counts_by_status_with_disabled_in_total_only(self):
        a1, a2, a3, _a4 = self.seats
        self.occupy(a1)
        self.hold(a2)
        Seat.objects.filter(pk=a3.pk).update(is_disabled=True, disabled_reason="Broken")
        counts = selectors.library_seat_counts(self.library)
        self.assertEqual(counts, {"total": 4, "empty": 1, "reserved": 1, "occupied": 1})

    def test_expired_holds_count_as_empty_and_removed_seats_are_not_counted(self):
        self.hold(self.seats[0], expires_at=timezone.now() - timedelta(minutes=1))
        Seat.objects.filter(pk=self.seats[1].pk).update(is_active=False)
        self.assertEqual(
            selectors.library_seat_counts(self.library), {"total": 3, "empty": 3, "reserved": 0, "occupied": 0}
        )

    def test_many_libraries_in_one_query_with_zeros_for_empty_ones(self):
        other, _, other_seats = bookable_library(name="Other Library", seats=2)
        empty = make_library(name="No Seats Library")
        self.occupy(self.seats[0])
        self.hold(other_seats[0])
        ids = [self.library.pk, other.pk, empty.pk]
        with self.assertNumQueries(1):
            counts = selectors.seat_counts_by_library(ids)
        self.assertEqual(counts[self.library.pk], {"total": 4, "empty": 3, "reserved": 0, "occupied": 1})
        self.assertEqual(counts[other.pk], {"total": 2, "empty": 1, "reserved": 1, "occupied": 0})
        self.assertEqual(counts[empty.pk], {"total": 0, "empty": 0, "reserved": 0, "occupied": 0})

    def test_holds_of_another_library_never_leak_into_the_figures(self):
        other, other_plan, other_seats = bookable_library(name="Other Library", seats=1)
        SeatHold.objects.create(
            seat=other_seats[0],
            library=other,
            kind="booking",
            student=make_student(),
            plan=other_plan,
            created_by=self.library.owner,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        self.assertEqual(selectors.library_seat_counts(self.library)["reserved"], 0)


class PublicSeatMapTests(StatusTestCase):
    def url(self, library=None):
        return f"/api/v1/libraries/{(library or self.library).pk}/seats/"

    def test_anonymous_sees_layout_status_and_counts_but_never_identities(self):
        student = make_student(name="Secret Student")
        self.occupy(self.seats[0])
        self.hold(self.seats[1], student=student)
        self.manual(self.seats[2], reason="Private owner reason")
        response = self.public.get(self.url())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = response.json()["data"]
        self.assertEqual([s["label"] for s in data["seats"]], ["A-1", "A-2", "A-3", "A-4"])
        self.assertEqual([s["status"] for s in data["seats"]], ["occupied", "reserved", "reserved", "empty"])
        self.assertEqual(set(data["seats"][0]), {"id", "label", "row_label", "position", "status"})
        self.assertEqual(data["counts"], {"total": 4, "empty": 1, "reserved": 2, "occupied": 1})
        body = response.content.decode()
        for secret in ("Secret Student", "Private owner reason", student.email, "student_name", "occupant"):
            self.assertNotIn(secret, body)

    def test_only_active_seats_are_listed_and_disabled_ones_show_as_disabled(self):
        Seat.objects.filter(pk=self.seats[0].pk).update(is_active=False)
        Seat.objects.filter(pk=self.seats[1].pk).update(is_disabled=True, disabled_reason="Broken")
        data = self.public.get(self.url()).json()["data"]
        self.assertEqual(
            {s["label"]: s["status"] for s in data["seats"]}, {"A-2": "disabled", "A-3": "empty", "A-4": "empty"}
        )

    def test_unpublished_inactive_and_unknown_libraries_are_404(self):
        draft = make_library(name="Draft Library")
        Seat.objects.create(library=draft, label="A-1")
        hidden, _, _ = bookable_library(name="Hidden Library", seats=1)
        Library.objects.filter(pk=hidden.pk).update(is_active=False)
        for library_id in (draft.pk, hidden.pk, "00000000-0000-0000-0000-000000000000"):
            self.assertEqual(self.public.get(f"/api/v1/libraries/{library_id}/seats/").status_code, 404)

    def test_query_count_is_flat(self):
        with CaptureQueriesContext(connection) as small:
            self.public.get(self.url())
        for seat in self.seats:
            self.hold(seat) if seat.position % 2 else self.occupy(seat)
        with CaptureQueriesContext(connection) as full:
            self.public.get(self.url())
        self.assertEqual(len(small), len(full))


class OwnerSeatMapTests(StatusTestCase):
    def test_owner_sees_status_occupant_and_hold_detail_for_own_seats(self):
        member = make_student(name="Asha Rao")
        membership = make_membership(library=self.library, plan=self.plan, seat=self.seats[0], student=member)
        booking = self.hold(self.seats[1], student=make_student(name="Ravi Kumar"))
        self.manual(self.seats[2], reason="Held for a walk-in")
        data = self.owner.get(OWNER_SEATS).json()["data"]
        by_label = {s["label"]: s for s in data["seats"]}
        self.assertEqual(by_label["A-1"]["status"], "occupied")
        self.assertEqual(by_label["A-1"]["occupant"], {"membership_id": str(membership.pk), "student_name": "Asha Rao"})
        self.assertIsNone(by_label["A-1"]["hold"])
        self.assertEqual(by_label["A-2"]["hold"]["kind"], "booking")
        self.assertEqual(by_label["A-2"]["hold"]["student_name"], "Ravi Kumar")
        self.assertEqual(by_label["A-2"]["hold"]["id"], str(booking.pk))
        self.assertIn("expires_at", by_label["A-2"]["hold"])
        self.assertEqual(by_label["A-3"]["hold"]["kind"], "owner_manual")
        self.assertEqual(by_label["A-3"]["hold"]["reason"], "Held for a walk-in")
        self.assertEqual(
            (by_label["A-4"]["status"], by_label["A-4"]["occupant"], by_label["A-4"]["hold"]), ("empty", None, None)
        )
        self.assertEqual(data["counts"], {"total": 4, "empty": 1, "reserved": 2, "occupied": 1})

    def test_include_inactive_lists_removed_seats_without_a_status(self):
        Seat.objects.filter(pk=self.seats[0].pk).update(is_active=False)
        data = self.owner.get(OWNER_SEATS, {"include_inactive": "true"}).json()["data"]
        removed = next(s for s in data["seats"] if s["label"] == "A-1")
        self.assertEqual((removed["is_active"], removed["status"]), (False, None))
        self.assertEqual(data["counts"]["total"], 3)

    def test_detail_cost_does_not_grow_with_the_number_of_seats(self):
        self.owner.get(OWNER_SEATS)  # warm-up: first request also loads the user and library
        with CaptureQueriesContext(connection) as before:
            self.owner.get(OWNER_SEATS)
        services.create_seats(library=self.library, actor=self.library.owner, specs=services.grid_specs(["B"], 20))
        for seat in self.seats:
            self.occupy(seat)
        with CaptureQueriesContext(connection) as after:
            self.owner.get(OWNER_SEATS)
        self.assertEqual(len(before), len(after))

    def test_another_owner_sees_none_of_it(self):
        self.occupy(self.seats[0])
        other, _, _ = bookable_library(name="Other Library", seats=1)
        data = client_for(other.owner).get(OWNER_SEATS).json()["data"]
        self.assertEqual([s["label"] for s in data["seats"]], ["A-1"])
        self.assertIsNone(data["seats"][0]["occupant"])
        self.assertEqual(data["counts"]["occupied"], 0)


class DeactivateAndDisableTests(StatusTestCase):
    def call(self, seat, action, reason="Desk is being replaced", client=None):
        return (client or self.owner).post(f"{OWNER_SEATS}{seat.pk}/{action}/", {"reason": reason}, format="json")

    def test_deactivating_a_free_seat_removes_it_and_keeps_the_row_as_history(self):
        seat = self.seats[0]
        response = self.call(seat, "deactivate")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual((data["is_active"], data["status"]), (False, None))
        seat.refresh_from_db()
        self.assertFalse(seat.is_active)
        self.assertEqual(Seat.objects.filter(pk=seat.pk).count(), 1)
        row = AuditLog.objects.get(action="seat.deactivate")
        self.assertEqual(
            (row.library_id, row.reason, row.entity_id), (self.library.pk, "Desk is being replaced", seat.pk)
        )
        self.assertNotIn("A-1", self.statuses())

    def test_a_removed_seats_history_survives_and_its_label_is_free_again(self):
        seat = self.seats[0]
        old = self.hold(seat, status="cancelled", closed_at=timezone.now())
        done = self.occupy(seat, state=Membership.State.ARCHIVED, archived_at=timezone.now())
        self.call(seat, "deactivate")
        services.create_seats(library=self.library, actor=self.library.owner, specs=[services.SeatSpec("A-1")])
        self.assertEqual(Seat.objects.filter(library=self.library, label="A-1").count(), 2)
        old.refresh_from_db()
        done.refresh_from_db()
        self.assertEqual((old.seat_id, done.seat_id), (seat.pk, seat.pk))

    def test_deactivating_a_disabled_seat_clears_the_maintenance_flag(self):
        seat = self.seats[0]
        self.call(seat, "disable", reason="Broken desk")
        self.assertEqual(self.call(seat, "deactivate").status_code, 200)
        seat.refresh_from_db()
        self.assertEqual((seat.is_active, seat.is_disabled, seat.disabled_reason), (False, False, ""))

    def test_removing_the_last_seat_unpublishes_the_library(self):
        library, plan, seats = bookable_library(name="Tiny Library", seats=1)
        self.assertTrue(library.is_published)
        response = self.call(seats[0], "deactivate", client=client_for(library.owner))
        self.assertEqual(response.status_code, 200)
        library.refresh_from_db()
        self.assertFalse(library.is_published)
        _ = plan

    def test_a_seat_in_use_cannot_be_removed_or_disabled(self):
        member_seat, held_seat, manual_seat, free_seat = self.seats
        self.occupy(member_seat)
        self.hold(held_seat)
        self.manual(manual_seat)
        for seat in (member_seat, held_seat, manual_seat):
            for action in ("deactivate", "disable"):
                response = self.call(seat, action)
                self.assertEqual(
                    (response.status_code, self.error_code(response)), (409, "SEAT_IN_USE"), (seat.label, action)
                )
            seat.refresh_from_db()
            self.assertEqual((seat.is_active, seat.is_disabled), (True, False))
        self.assertFalse(AuditLog.objects.filter(action__in=["seat.deactivate", "seat.disable"]).exists())
        self.assertEqual(self.call(free_seat, "disable").status_code, 200)

    def test_an_overdue_member_still_blocks_removal(self):
        self.occupy(self.seats[0], due_in=-30, start_date=TODAY - timedelta(days=90))
        self.assertEqual(self.error_code(self.call(self.seats[0], "deactivate")), "SEAT_IN_USE")

    def test_dead_holds_and_archived_members_do_not_block(self):
        self.hold(self.seats[0], expires_at=timezone.now() - timedelta(seconds=1))
        self.occupy(self.seats[1], state=Membership.State.ARCHIVED, archived_at=timezone.now())
        self.assertEqual(self.call(self.seats[0], "deactivate").status_code, 200)
        self.assertEqual(self.call(self.seats[1], "disable").status_code, 200)

    def test_disable_stores_the_reason_and_blocks_booking_and_manual_holds(self):
        seat = self.seats[0]
        response = self.call(seat, "disable", reason="Broken chair")
        data = response.json()["data"]
        self.assertEqual(
            (data["is_disabled"], data["disabled_reason"], data["status"]), (True, "Broken chair", "disabled")
        )
        row = AuditLog.objects.get(action="seat.disable")
        self.assertEqual((row.library_id, row.reason), (self.library.pk, "Broken chair"))
        booking = client_for(make_student()).post(
            "/api/v1/student/holds/", {"seat_id": str(seat.pk), "plan_id": str(self.plan.pk)}, format="json"
        )
        self.assertEqual(self.error_code(booking), "SEAT_UNAVAILABLE")
        manual = self.owner.post(f"{OWNER_SEATS}{seat.pk}/manual-hold/", {"reason": "Reserved"}, format="json")
        self.assertEqual(self.error_code(manual), "SEAT_UNAVAILABLE")
        self.assertEqual(
            self.public.get(f"/api/v1/libraries/{self.library.pk}/seats/").json()["data"]["seats"][0]["status"],
            "disabled",
        )

    def test_enable_returns_the_seat_to_service(self):
        seat = self.seats[0]
        self.call(seat, "disable")
        response = self.owner.post(f"{OWNER_SEATS}{seat.pk}/enable/")
        self.assertEqual((response.status_code, response.json()["data"]["status"]), (200, "empty"))
        self.assertEqual(
            client_for(make_student())
            .post("/api/v1/student/holds/", {"seat_id": str(seat.pk), "plan_id": str(self.plan.pk)}, format="json")
            .status_code,
            201,
        )

    def test_both_actions_are_idempotent_without_extra_audit_rows(self):
        for action, audit_action in (("deactivate", "seat.deactivate"), ("disable", "seat.disable")):
            seat = self.seats[0] if action == "disable" else self.seats[1]
            self.assertEqual(self.call(seat, action).status_code, 200)
            self.assertEqual(self.call(seat, action).status_code if action == "disable" else 200, 200)
            if action == "deactivate":
                self.assertEqual(self.call(seat, action).status_code, 200)
            self.assertEqual(AuditLog.objects.filter(action=audit_action).count(), 1)

    def test_a_removed_seat_cannot_be_disabled(self):
        self.call(self.seats[0], "deactivate")
        self.assertEqual(self.call(self.seats[0], "disable").status_code, 404)

    def test_reason_is_required(self):
        for action in ("deactivate", "disable"):
            for payload in ({}, {"reason": "no"}, {"reason": "x" * 201}):
                response = self.owner.post(f"{OWNER_SEATS}{self.seats[0].pk}/{action}/", payload, format="json")
                self.assertEqual(response.status_code, 400, (action, payload))
        self.seats[0].refresh_from_db()
        self.assertTrue(self.seats[0].is_active)

    def test_isolation_and_roles(self):
        other, _, other_seats = bookable_library(name="Other Library", seats=1)
        for action in ("deactivate", "disable"):
            response = self.call(other_seats[0], action)
            self.assertEqual((response.status_code, self.error_code(response)), (404, "NOT_FOUND"))
        other_seats[0].refresh_from_db()
        self.assertEqual((other_seats[0].is_active, other_seats[0].is_disabled), (True, False))
        self.assertEqual(self.call(self.seats[0], "disable", client=client_for(make_student())).status_code, 403)
        self.assertEqual(self.call(self.seats[0], "deactivate", client=APIClient()).status_code, 401)
        self.assertEqual(self.call(self.seats[0], "disable", client=client_for(make_owner())).status_code, 409)
        _ = other


class DiscoveryIntegrationTests(StatusTestCase):
    """Library seat_counts and sort=available now come from the real seat status (SEAT-08, DIS-03)."""

    def test_discovery_shows_live_counts_and_sorts_by_free_seats(self):
        busy, busy_plan, busy_seats = bookable_library(name="Busy Library", seats=3)
        for seat in busy_seats[:2]:
            make_membership(library=busy, plan=busy_plan, seat=seat, student=make_student())
        self.hold(self.seats[0])
        response = self.public.get("/api/v1/libraries/", {"sort": "available"})
        self.assertEqual(response.status_code, 200, response.content)
        items = response.json()["data"]["items"]
        self.assertEqual([i["name"] for i in items], [self.library.name, "Busy Library"])
        self.assertEqual(items[0]["seat_counts"], {"total": 4, "empty": 3, "reserved": 1, "occupied": 0})
        self.assertEqual(items[1]["seat_counts"], {"total": 3, "empty": 1, "reserved": 0, "occupied": 2})

    def test_detail_has_seat_counts_and_discovery_cost_stays_flat(self):
        detail = self.public.get(f"/api/v1/libraries/{self.library.pk}/").json()["data"]
        self.assertEqual(detail["seat_counts"], {"total": 4, "empty": 4, "reserved": 0, "occupied": 0})
        with CaptureQueriesContext(connection) as one:
            self.public.get("/api/v1/libraries/", {"sort": "available"})
        for n in range(3):
            bookable_library(name=f"Library {n}", seats=2)
        with CaptureQueriesContext(connection) as many:
            self.public.get("/api/v1/libraries/", {"sort": "available"})
        self.assertEqual(len(one), len(many))
