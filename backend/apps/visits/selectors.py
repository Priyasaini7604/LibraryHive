"""Read-side queries for visit requests (BACKEND_ARCHITECTURE.md section 8)."""

from datetime import date

from django.db.models import QuerySet

from .models import VisitRequest


def _base() -> QuerySet[VisitRequest]:
    return VisitRequest.objects.select_related("library", "student")


def student_visits(student, *, status: str | None = None) -> QuerySet[VisitRequest]:
    queryset = _base().filter(student=student)
    return queryset.filter(status=status) if status else queryset


def owner_visits(
    library, *, status: str | None = None, date_from: date | None = None, date_to: date | None = None
) -> QuerySet[VisitRequest]:
    queryset = _base().filter(library=library)
    if status:
        queryset = queryset.filter(status=status)
    if date_from:
        queryset = queryset.filter(preferred_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(preferred_date__lte=date_to)
    return queryset.order_by("preferred_date", "-created_at")


def pending_count(library) -> int:
    return VisitRequest.objects.filter(library=library, status=VisitRequest.Status.PENDING).count()
