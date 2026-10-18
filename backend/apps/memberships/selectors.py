"""Read-side queries for memberships (BACKEND_ARCHITECTURE.md section 8, SPEC.md 3.10).

Other apps read membership facts only through these functions, never through
the model, so the status rules live in one place.
"""

from datetime import date, timedelta

from django.conf import settings
from django.db.models import Case, CharField, Exists, OuterRef, QuerySet, Value, When

from apps.core.dates import business_today

from .models import Membership

ACTIVE = "active"
DUE = "due"
OVERDUE = "overdue"
ARCHIVED = "archived"


def annotate_status(queryset: QuerySet[Membership], *, today: date | None = None) -> QuerySet[Membership]:
    """Add `status`: archived, overdue, due or active, computed in SQL (decision D5).

    "Today" is the Asia/Kolkata business date. A membership is due from three
    days before `next_due_date` up to and including that date, and overdue the
    day after.
    """
    today = today or business_today()
    due_from = today + timedelta(days=settings.MEMBERSHIP_DUE_WINDOW_DAYS)
    return queryset.annotate(
        status=Case(
            When(state=Membership.State.ARCHIVED, then=Value(ARCHIVED)),
            When(next_due_date__lt=today, then=Value(OVERDUE)),
            When(next_due_date__lte=due_from, then=Value(DUE)),
            default=Value(ACTIVE),
            output_field=CharField(),
        )
    )


def active_membership_exists(seat) -> bool:
    """True if the seat has a non-archived membership: it is *occupied* (SPEC.md 4.1 rule 2).

    Called by `seats` (imported lazily there, so `seats` never imports memberships models) and by
    every writer of seat availability inside its seat lock.
    """
    return Membership.objects.filter(seat=seat, state=Membership.State.ACTIVE).exists()


def student_is_member(student, library) -> bool:
    """True if the student holds a non-archived membership at the library (ALREADY_MEMBER check)."""
    return Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE).exists()


def current_membership(student, library) -> Membership | None:
    """The student's non-archived membership at the library with its derived `status`, or None."""
    return annotate_status(
        Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE)
    ).first()


def occupied_expression(seat_ref: str = "pk") -> Exists:
    """An `EXISTS` expression: the outer seat has a non-archived membership (it is occupied, SPEC.md 4.1 rule 2).

    Lets `seats` derive the status of a whole library in one query without importing the model.
    """
    return Exists(Membership.objects.filter(seat=OuterRef(seat_ref), state=Membership.State.ACTIVE))


def active_occupants(seat_ids) -> dict:
    """{seat_id: {"membership_id", "student_name"}} for the non-archived memberships on these seats.

    Owner-only detail: the public seat map never shows who sits where (SPEC.md 4.1).
    """
    rows = Membership.objects.filter(seat_id__in=list(seat_ids), state=Membership.State.ACTIVE).select_related(
        "student"
    )
    return {row.seat_id: {"membership_id": row.pk, "student_name": row.student.name} for row in rows}
