"""Membership model constraints and derived status (SPEC.md 3.10, decision D5)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import count
from unittest import mock

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from apps.core.dates import business_today
from apps.core.tests.factories import make_owner, make_student
from apps.libraries.tests.base import make_library, make_plan
from apps.memberships import selectors
from apps.memberships.models import Membership
from apps.seats.models import Seat

TODAY = business_today()  # the real business date, so fixtures never drift from the code under test
_seat_numbers = count(1)


def make_membership(
    *, library=None, plan=None, student=None, seat=None, today=TODAY, due_in=30, **overrides
) -> Membership:
    library = library or make_library(make_owner())
    seat = seat or Seat.objects.create(library=library, label=f"T{next(_seat_numbers)}")
    plan = plan or make_plan(library)
    student = student or make_student()
    values = {
        "student": student,
        "library": library,
        "seat": seat,
        "plan": plan,
        "source": Membership.Source.ONLINE,
        "state": Membership.State.ACTIVE,
        "start_date": today - timedelta(days=1),
        "next_due_date": today + timedelta(days=due_in),
        "created_by": student,
        **overrides,
    }
    return Membership.objects.create(**values)


def status_of(membership: Membership, today: date = TODAY) -> str:
    return selectors.annotate_status(Membership.objects.filter(pk=membership.pk), today=today).get().status


class DerivedStatusTests(TestCase):
    def setUp(self):
        self.library = make_library(make_owner())
        self.plan = make_plan(self.library)

    def membership(self, due_in, **overrides):
        return make_membership(library=self.library, plan=self.plan, due_in=due_in, **overrides)

    def test_boundaries(self):
        cases = {
            -1: selectors.OVERDUE,  # yesterday
            0: selectors.DUE,  # today
            1: selectors.DUE,
            3: selectors.DUE,  # today + 3 is the last due day
            4: selectors.ACTIVE,
            30: selectors.ACTIVE,
        }
        for due_in, expected in cases.items():
            membership = self.membership(due_in, start_date=TODAY - timedelta(days=60))
            self.assertEqual(status_of(membership), expected, f"next_due_date = today {due_in:+d}")

    def test_far_overdue_is_still_overdue(self):
        membership = self.membership(-40, start_date=TODAY - timedelta(days=90))
        self.assertEqual(status_of(membership), selectors.OVERDUE)

    def test_archived_wins_over_every_date(self):
        for due_in in (-5, 0, 2, 20):
            membership = self.membership(
                due_in,
                start_date=TODAY - timedelta(days=60),
                state=Membership.State.ARCHIVED,
                archived_at=timezone.now(),
                student=make_student(),
            )
            self.assertEqual(status_of(membership), selectors.ARCHIVED)

    def test_due_window_follows_the_setting(self):
        membership = self.membership(5, start_date=TODAY - timedelta(days=60))
        self.assertEqual(status_of(membership), selectors.ACTIVE)
        with self.settings(MEMBERSHIP_DUE_WINDOW_DAYS=7):
            self.assertEqual(status_of(membership), selectors.DUE)

    def test_today_is_the_kolkata_date_not_the_utc_date(self):
        # 20:30 UTC on 18 Oct is 02:00 IST on 19 Oct: a membership due on the 18th is already overdue.
        due = date(2026, 10, 18)  # a fixed date: the instant below is fixed too
        membership = self.membership((due - TODAY).days, start_date=due - timedelta(days=60))
        instant = datetime(2026, 10, 18, 20, 30, tzinfo=UTC)
        with mock.patch("django.utils.timezone.now", return_value=instant):
            default_today = selectors.annotate_status(Membership.objects.filter(pk=membership.pk)).get().status
        self.assertEqual(default_today, selectors.OVERDUE)

    def test_annotation_filters_and_counts_in_one_query(self):
        for due_in, student in [(-2, make_student()), (1, make_student()), (20, make_student())]:
            self.membership(due_in, start_date=TODAY - timedelta(days=60), student=student)
        annotated = selectors.annotate_status(Membership.objects.filter(library=self.library), today=TODAY)
        with self.assertNumQueries(1):
            result = {m.status for m in annotated}
        self.assertEqual(result, {selectors.OVERDUE, selectors.DUE, selectors.ACTIVE})
        self.assertEqual(annotated.filter(status=selectors.OVERDUE).count(), 1)


class ConstraintTests(TestCase):
    def setUp(self):
        self.library = make_library(make_owner())
        self.plan = make_plan(self.library)
        self.student = make_student()

    def make(self, **overrides):
        return make_membership(library=self.library, plan=self.plan, student=self.student, **overrides)

    def test_one_active_membership_per_student_and_library(self):
        self.make()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make()

    def test_archived_history_does_not_block_a_new_membership(self):
        self.make(state=Membership.State.ARCHIVED, archived_at=timezone.now())
        self.make()
        self.assertEqual(Membership.objects.filter(student=self.student).count(), 2)

    def test_same_student_can_join_another_library(self):
        self.make()
        other = make_library(make_owner(), name="Other Library")
        make_membership(library=other, plan=make_plan(other), student=self.student)
        self.assertEqual(Membership.objects.filter(student=self.student).count(), 2)

    def test_archived_requires_archived_at(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(state=Membership.State.ARCHIVED)

    def test_due_date_must_follow_start_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(start_date=TODAY, next_due_date=TODAY)

    def test_unknown_source_or_state_is_refused(self):
        for overrides in ({"source": "walk_in"}, {"state": "paused"}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.make(**overrides)

    def test_history_rows_cannot_be_deleted_with_their_parents(self):
        membership = self.make()
        for target in (self.plan, self.library, self.student):
            with self.assertRaises(ProtectedError):
                target.delete()
        self.assertTrue(Membership.objects.filter(pk=membership.pk).exists())

    def test_losing_a_race_maps_to_already_member(self):
        from apps.core.exceptions import lookup_constraint_error

        status, code, _ = lookup_constraint_error("membership_one_live_per_student_library")
        self.assertEqual((status, code), (409, "ALREADY_MEMBER"))


class SelectorTests(TestCase):
    def setUp(self):
        self.library = make_library(make_owner())
        self.plan = make_plan(self.library, price=Decimal("900.00"))
        self.student = make_student()

    def test_student_is_member_only_for_non_archived_memberships_here(self):
        self.assertFalse(selectors.student_is_member(self.student, self.library))
        make_membership(
            library=self.library,
            plan=self.plan,
            student=self.student,
            state=Membership.State.ARCHIVED,
            archived_at=timezone.now(),
        )
        self.assertFalse(selectors.student_is_member(self.student, self.library))
        make_membership(library=self.library, plan=self.plan, student=self.student)
        self.assertTrue(selectors.student_is_member(self.student, self.library))

    def test_membership_at_another_library_does_not_count(self):
        other = make_library(make_owner(), name="Other Library")
        make_membership(library=other, plan=make_plan(other), student=self.student)
        self.assertFalse(selectors.student_is_member(self.student, self.library))
        self.assertIsNone(selectors.current_membership(self.student, self.library))

    def test_current_membership_returns_the_live_one_with_status(self):
        make_membership(
            library=self.library,
            plan=self.plan,
            student=self.student,
            state=Membership.State.ARCHIVED,
            archived_at=timezone.now(),
        )
        today = business_today()
        live = make_membership(library=self.library, plan=self.plan, student=self.student, today=today, due_in=2)
        current = selectors.current_membership(self.student, self.library)
        self.assertEqual(current.pk, live.pk)
        self.assertEqual(current.status, selectors.DUE)
