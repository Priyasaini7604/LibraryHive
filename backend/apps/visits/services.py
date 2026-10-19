"""Visit request state changes (SPEC.md 4.11, BACKEND_ARCHITECTURE.md #77, #79, #81).

Notifications use the SPEC.md 4.5 key `visit:{visit_id}:{status}:{recipient_id}`.
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.dates import business_today
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.libraries.models import Library
from apps.notifications import services as notifications

from .models import VisitRequest

logger = logging.getLogger("apps.visits")

MAX_DAYS_AHEAD = 60


def _pending_exists() -> Conflict:
    return Conflict("You already have a pending visit request for this library.", code="VISIT_PENDING_EXISTS")


@transaction.atomic
def request_visit(*, student, library_id, preferred_date, preferred_slot: str, student_note: str = "") -> VisitRequest:
    """Ask to visit a published library (#77, DEMO-01). One pending request per student and library."""
    library = Library.objects.select_related("owner").filter(pk=library_id, is_published=True, is_active=True).first()
    if library is None:
        raise Conflict("This library is not accepting visit requests.", code="LIBRARY_NOT_BOOKABLE")
    today = business_today()
    if not today <= preferred_date <= today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationFailed(details={"preferred_date": ["Choose a date within the next 60 days."]})
    if VisitRequest.objects.filter(student=student, library=library, status=VisitRequest.Status.PENDING).exists():
        raise _pending_exists()
    try:
        with transaction.atomic():
            visit = VisitRequest.objects.create(
                student=student,
                library=library,
                preferred_date=preferred_date,
                preferred_slot=preferred_slot,
                student_note=student_note.strip(),
            )
    except IntegrityError:
        raise _pending_exists() from None
    notifications.notify(
        recipient=library.owner,
        type="visit_requested",
        title="New visit request",
        body=f"{student.name} wants to visit on {preferred_date:%d %b %Y} ({preferred_slot}).",
        dedup_key=f"visit:{visit.pk}:pending:{library.owner_id}",
        entity=("visit", visit.pk),
    )
    logger.info("Visit requested", extra={"visit_id": str(visit.pk), "student_id": str(student.pk)})
    return visit


def _locked(visit_id, **scope) -> VisitRequest:
    try:
        return (
            VisitRequest.objects.select_for_update(of=("self",))
            .select_related("student", "library")
            .get(pk=visit_id, **scope)
        )
    except (VisitRequest.DoesNotExist, ValueError, TypeError):
        raise NotFound() from None


def _only_pending(visit: VisitRequest) -> None:
    if visit.status != VisitRequest.Status.PENDING:
        raise Conflict(f"This request is already {visit.status}.", code="INVALID_TRANSITION")


@transaction.atomic
def cancel_visit(*, student, visit_id) -> VisitRequest:
    """The student withdraws a pending request (#79, DEMO-05)."""
    visit = _locked(visit_id, student=student)
    _only_pending(visit)
    visit.status = VisitRequest.Status.CANCELLED
    visit.save(update_fields=["status", "updated_at"])
    return visit


@transaction.atomic
def decide(*, library, owner, visit_id, decision: str, owner_note: str = "") -> VisitRequest:
    """The owner accepts or rejects a pending request (#81, DEMO-03). Audited; the student is notified."""
    visit = _locked(visit_id, library=library)
    _only_pending(visit)
    visit.status = VisitRequest.Status.ACCEPTED if decision == "accept" else VisitRequest.Status.REJECTED
    visit.owner_note = owner_note.strip()
    visit.decided_at = timezone.now()
    visit.decided_by = owner
    visit.save()
    audit.record(
        actor=owner,
        action="visit.decide",
        entity_type="visit",
        entity_id=visit.pk,
        library=library,
        changes={"status": ["pending", visit.status]},
    )
    notifications.notify(
        recipient=visit.student,
        type="visit_decided",
        title=f"Your visit request was {visit.status}",
        body=f"{library.name} {visit.status} your visit on {visit.preferred_date:%d %b %Y}.",
        dedup_key=f"visit:{visit.pk}:{visit.status}:{visit.student_id}",
        entity=("visit", visit.pk),
    )
    return visit
