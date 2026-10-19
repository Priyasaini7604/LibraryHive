"""Read-side queries for attendance (BACKEND_ARCHITECTURE.md section 8)."""

from datetime import date

from django.db.models import QuerySet, Sum

from apps.core.dates import business_today

from .models import AttendanceRecord


def _base() -> QuerySet[AttendanceRecord]:
    return AttendanceRecord.objects.select_related("student", "library", "seat")


def current_record(student) -> AttendanceRecord | None:
    """The student's open record anywhere, or None (#65)."""
    return _base().filter(student=student, check_out_at__isnull=True).first()


def student_records(student, *, month: tuple[int, int] | None = None) -> QuerySet[AttendanceRecord]:
    queryset = _base().filter(student=student)
    if month:
        queryset = queryset.filter(date__year=month[0], date__month=month[1])
    return queryset


def summary(queryset: QuerySet[AttendanceRecord]) -> dict:
    """Days present (distinct dates) and total minutes over a set of records."""
    return {
        "days_present": queryset.values("date").distinct().count(),
        "total_minutes": queryset.aggregate(total=Sum("duration_minutes"))["total"] or 0,
    }


def live_roster(library) -> QuerySet[AttendanceRecord]:
    """Who is present now: the library's open records (#66)."""
    return _base().filter(library=library, check_out_at__isnull=True).order_by("check_in_at")


def owner_records(
    library,
    *,
    date_: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    student_id=None,
) -> QuerySet[AttendanceRecord]:
    queryset = _base().filter(library=library)
    if date_:
        queryset = queryset.filter(date=date_)
    if date_from:
        queryset = queryset.filter(date__gte=date_from)
    if date_to:
        queryset = queryset.filter(date__lte=date_to)
    if student_id:
        queryset = queryset.filter(student_id=student_id)
    return queryset


def present_now_count(library) -> int:
    return AttendanceRecord.objects.filter(library=library, check_out_at__isnull=True).count()


def check_ins_today(library, *, today: date | None = None) -> int:
    return AttendanceRecord.objects.filter(library=library, date=today or business_today()).count()


def member_summary(library, student, *, today: date | None = None) -> dict:
    """This month's days present and the last check-in of one member at one library (#51)."""
    today = today or business_today()
    records = AttendanceRecord.objects.filter(library=library, student=student)
    month = records.filter(date__year=today.year, date__month=today.month)
    last = records.order_by("-check_in_at").values_list("check_in_at", flat=True).first()
    return {"this_month_days": month.values("date").distinct().count(), "last_check_in": last}
