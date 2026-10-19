"""Membership.seat, one occupant per seat and active_membership_exists (SPEC.md 3.10, 4.1; T11 completion)."""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.core.exceptions import lookup_constraint_error
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.tests.base import make_library, make_plan
from apps.memberships import selectors
from apps.memberships.models import Membership
from apps.memberships.tests.test_membership_model import TODAY, make_membership
from apps.seats.models import Seat


class SeatConstraintTests(TestCase):
    def setUp(self):
        self.library = make_library(make_owner())
        self.plan = make_plan(self.library)
        self.seat = Seat.objects.create(library=self.library, label="A-1")

    def join(self, seat=None, **overrides):
        return make_membership(library=self.library, plan=self.plan, seat=seat or self.seat, **overrides)

    def test_one_active_membership_per_seat_even_for_different_students(self):
        self.join()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.join(student=make_student())

    def test_an_archived_membership_frees_the_seat_and_keeps_it_as_history(self):
        old = self.join(state=Membership.State.ARCHIVED, archived_at=timezone.now())
        self.join(student=make_student())  # the seat can be taken again
        old.refresh_from_db()
        self.assertEqual(old.seat_id, self.seat.pk)  # the FK is not cleared on archival
        self.assertEqual(Membership.objects.filter(seat=self.seat).count(), 2)

    def test_different_seats_do_not_conflict(self):
        self.join()
        self.join(seat=Seat.objects.create(library=self.library, label="A-2"), student=make_student())

    def test_a_seat_with_membership_history_cannot_be_deleted(self):
        self.join()
        with self.assertRaises(ProtectedError):
            self.seat.delete()

    def test_losing_the_seat_race_maps_to_seat_unavailable(self):
        status, code, _ = lookup_constraint_error("membership_one_live_per_seat")
        self.assertEqual((status, code), (409, "SEAT_UNAVAILABLE"))


class ActiveMembershipExistsTests(TestCase):
    def setUp(self):
        self.library = make_library(make_owner())
        self.plan = make_plan(self.library)
        self.seat = Seat.objects.create(library=self.library, label="A-1")

    def test_false_for_a_seat_nobody_holds(self):
        self.assertFalse(selectors.active_membership_exists(self.seat))

    def test_true_while_a_membership_is_active_whatever_its_due_date(self):
        make_membership(
            library=self.library, plan=self.plan, seat=self.seat, due_in=-30, start_date=TODAY - timedelta(days=90)
        )  # overdue still occupies
        self.assertTrue(selectors.active_membership_exists(self.seat))

    def test_false_once_archived(self):
        make_membership(
            library=self.library,
            plan=self.plan,
            seat=self.seat,
            state=Membership.State.ARCHIVED,
            archived_at=timezone.now(),
        )
        self.assertFalse(selectors.active_membership_exists(self.seat))

    def test_other_seats_are_unaffected(self):
        other = Seat.objects.create(library=self.library, label="A-2")
        make_membership(library=self.library, plan=self.plan, seat=self.seat)
        self.assertFalse(selectors.active_membership_exists(other))

    def test_is_a_single_cheap_query(self):
        with self.assertNumQueries(1):
            selectors.active_membership_exists(self.seat)
