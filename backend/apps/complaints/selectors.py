"""Read-side queries for complaints (BACKEND_ARCHITECTURE.md section 8)."""

from django.db.models import QuerySet

from .models import Complaint


def _base() -> QuerySet[Complaint]:
    return Complaint.objects.select_related("library", "student", "membership__seat")


def student_complaints(student, *, status: str | None = None) -> QuerySet[Complaint]:
    queryset = _base().filter(student=student)
    return queryset.filter(status=status) if status else queryset


def student_complaint(student, complaint_id) -> Complaint | None:
    return _base().filter(student=student, pk=complaint_id).first()


def owner_complaints(library, *, status: str | None = None, category: str | None = None) -> QuerySet[Complaint]:
    queryset = _base().filter(library=library)
    if status:
        queryset = queryset.filter(status=status)
    if category:
        queryset = queryset.filter(category=category)
    return queryset


def owner_complaint(library, complaint_id) -> Complaint | None:
    return _base().filter(library=library, pk=complaint_id).first()


def open_count(library) -> int:
    """Complaints still waiting for the owner (open or in progress); the dashboard number (#82)."""
    return Complaint.objects.filter(library=library).exclude(status=Complaint.Status.RESOLVED).count()


def counts_by(library, field: str, *, date_from=None, date_to=None) -> dict[str, int]:
    """Complaint counts grouped by `status` or `category`, optionally by creation date (#85)."""
    from django.db.models import Count

    queryset = Complaint.objects.filter(library=library)
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return {row[field]: row["n"] for row in queryset.values(field).annotate(n=Count("id"))}


def student_open_count(student) -> int:
    """The student's own complaints that are not resolved yet (student dashboard)."""
    return Complaint.objects.filter(student=student).exclude(status=Complaint.Status.RESOLVED).count()


def count_for_member(library, student) -> int:
    """How many complaints this student has raised at this library (#51)."""
    return Complaint.objects.filter(library=library, student=student).count()
