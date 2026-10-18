"""Read-side queries for memberships (BACKEND_ARCHITECTURE.md section 8, SPEC.md 3.10).

Other apps read membership facts only through these functions, never through
the model, so the status rules live in one place.
"""

from datetime import date, timedelta

from django.conf import settings
from django.db.models import Case, CharField, QuerySet, Value, When

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


def student_is_member(student, library) -> bool:
    """True if the student holds a non-archived membership at the library (ALREADY_MEMBER check)."""
    return Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE).exists()


def current_membership(student, library) -> Membership | None:
    """The student's non-archived membership at the library with its derived `status`, or None."""
    return annotate_status(
        Membership.objects.filter(student=student, library=library, state=Membership.State.ACTIVE)
    ).first()
