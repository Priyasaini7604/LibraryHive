"""Complaint state changes (SPEC.md 4.10, BACKEND_ARCHITECTURE.md #71, #76).

Notifications use the SPEC.md 4.5 key `complaint:{complaint_id}:{status}:{recipient_id}`.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.libraries.models import Library
from apps.memberships.models import Membership
from apps.notifications import services as notifications

from .models import Complaint

logger = logging.getLogger("apps.complaints")


@transaction.atomic
def create_complaint(*, student, library_id, category: str, description: str) -> Complaint:
    """A member (current or past) raises a complaint about a library (#71, CMP-01). The owner is notified."""
    library = Library.objects.select_related("owner").filter(pk=library_id).first()
    membership = (
        Membership.objects.filter(student=student, library_id=library_id).order_by("-created_at").first()
        if library
        else None
    )
    if library is None or membership is None:
        raise Conflict("Only members of this library can raise a complaint.", code="NO_ACTIVE_MEMBERSHIP")
    complaint = Complaint.objects.create(
        student=student,
        library=library,
        membership=membership,
        category=category,
        description=description.strip(),
    )
    notifications.notify(
        recipient=library.owner,
        type="complaint_created",
        title="New complaint",
        body=f"{student.name} raised a {complaint.get_category_display().lower()} complaint.",
        dedup_key=f"complaint:{complaint.pk}:open:{library.owner_id}",
        entity=("complaint", complaint.pk),
    )
    logger.info("Complaint created", extra={"complaint_id": str(complaint.pk), "student_id": str(student.pk)})
    return complaint


@transaction.atomic
def respond(*, library, owner, complaint_id, status: str | None = None, owner_response: str | None = None) -> Complaint:
    """The owner answers a complaint and/or moves its status (#76, CMP-04).

    `resolved` needs a non-empty response (given now or earlier). A resolved complaint is final. Audited,
    and the student is notified.
    """
    try:
        complaint = (
            Complaint.objects.select_for_update(of=("self",))
            .select_related("student", "library")
            .get(pk=complaint_id, library=library)
        )
    except (Complaint.DoesNotExist, ValueError, TypeError):
        raise NotFound() from None
    if complaint.status == Complaint.Status.RESOLVED:
        raise Conflict("This complaint is already resolved.", code="INVALID_TRANSITION")

    new_status = status or complaint.status
    if new_status != complaint.status and new_status not in Complaint.TRANSITIONS[complaint.status]:
        raise Conflict(f"A complaint cannot go from {complaint.status} to {new_status}.", code="INVALID_TRANSITION")
    response = complaint.owner_response if owner_response is None else owner_response.strip()
    if new_status == Complaint.Status.RESOLVED and not response:
        raise ValidationFailed(
            "Write a response before resolving.", details={"owner_response": ["Required to resolve."]}
        )
    if new_status == complaint.status and owner_response is None:
        raise ValidationFailed("Nothing to change.")

    now = timezone.now()
    before = {"status": complaint.status, "responded": bool(complaint.owner_response)}
    complaint.status = new_status
    if owner_response is not None and response:
        complaint.owner_response = response
        complaint.responded_at = now
    if new_status == Complaint.Status.RESOLVED:
        complaint.resolved_at = now
        complaint.resolved_by = owner
        complaint.responded_at = complaint.responded_at or now
    complaint.save()
    audit.record(
        actor=owner,
        action="complaint.update",
        entity_type="complaint",
        entity_id=complaint.pk,
        library=library,
        changes={"before": before, "after": {"status": new_status, "responded": bool(complaint.owner_response)}},
    )
    notifications.notify(
        recipient=complaint.student,
        type="complaint_updated",
        title="Your complaint was updated",
        body=f"{library.name} marked your complaint {complaint.get_status_display().lower()}.",
        dedup_key=f"complaint:{complaint.pk}:{new_status}:{complaint.student_id}",
        entity=("complaint", complaint.pk),
    )
    return complaint
