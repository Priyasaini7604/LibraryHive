"""Attendance state changes (SPEC.md 4.9, BACKEND_ARCHITECTURE.md #62-#70).

Check-in locks the member's membership row so a double tap is serialised; `attendance_one_open_per_student` is
the database backstop. Every owner action is audited.
"""

import logging
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.dates import business_now
from apps.core.exceptions import Conflict, NotFound, ValidationFailed
from apps.memberships.models import Membership

from .models import AttendanceRecord

logger = logging.getLogger("apps.attendance")

DEFAULT_CLOSING = time(23, 59)


def _duration(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def _close(record: AttendanceRecord, *, at: datetime, method: str, status: str = AttendanceRecord.Status.CLOSED):
    record.check_out_at = at
    record.check_out_method = method
    record.status = status
    record.duration_minutes = _duration(record.check_in_at, at)
    record.save()


def _already_checked_in() -> Conflict:
    return Conflict("You are already checked in.", code="ALREADY_CHECKED_IN")


def _create_record(*, membership: Membership, method: str) -> AttendanceRecord:
    """Open a record for a *locked*, active membership. A second open record anywhere is refused."""
    if AttendanceRecord.objects.filter(student_id=membership.student_id, check_out_at__isnull=True).exists():
        raise _already_checked_in()
    now = timezone.now()
    try:
        with transaction.atomic():
            return AttendanceRecord.objects.create(
                student_id=membership.student_id,
                library_id=membership.library_id,
                membership=membership,
                seat_id=membership.seat_id,
                date=timezone.localtime(now).date(),
                check_in_at=now,
                check_in_method=method,
            )
    except IntegrityError:
        raise _already_checked_in() from None


@transaction.atomic
def check_in(*, student, library_id) -> AttendanceRecord:
    """The student checks in at a library where they hold a non-archived membership (#62, ATT-01)."""
    try:
        membership = (
            Membership.objects.select_for_update(of=("self",))
            .select_related("seat", "library")
            .filter(student=student, library_id=library_id, state=Membership.State.ACTIVE)
            .first()
        )
    except (ValueError, TypeError):
        membership = None
    if membership is None:
        raise Conflict("You do not have an active membership at this library.", code="NO_ACTIVE_MEMBERSHIP")
    record = _create_record(membership=membership, method=AttendanceRecord.Method.SELF)
    logger.info("Student checked in", extra={"record_id": str(record.pk), "student_id": str(student.pk)})
    return record


@transaction.atomic
def check_out(*, student) -> AttendanceRecord:
    """The student closes their open record (#63, ATT-02)."""
    record = (
        AttendanceRecord.objects.select_for_update(of=("self",))
        .select_related("library", "seat")
        .filter(student=student, check_out_at__isnull=True)
        .first()
    )
    if record is None:
        raise ValidationFailed("You are not checked in.", code="NOT_CHECKED_IN")
    _close(record, at=_after(record), method=AttendanceRecord.Method.SELF)
    logger.info("Student checked out", extra={"record_id": str(record.pk), "student_id": str(student.pk)})
    return record


def _after(record: AttendanceRecord) -> datetime:
    """Now, but never at or before the check-in (the database requires check-out > check-in)."""
    return max(timezone.now(), record.check_in_at + timedelta(seconds=1))


@transaction.atomic
def owner_check_in(*, library, owner, membership_id) -> AttendanceRecord:
    """The owner checks a member in by hand (#68, ATT-06). Same rules as the student's own check-in."""
    try:
        membership = (
            Membership.objects.select_for_update(of=("self",))
            .select_related("seat", "library")
            .filter(pk=membership_id, library=library)
            .first()
        )
    except (ValueError, TypeError):
        membership = None
    if membership is None:
        raise NotFound()
    if membership.state != Membership.State.ACTIVE:
        raise Conflict("This membership has been archived.", code="NO_ACTIVE_MEMBERSHIP")
    record = _create_record(membership=membership, method=AttendanceRecord.Method.OWNER)
    audit.record(
        actor=owner,
        action="attendance.check_in",
        entity_type="attendance_record",
        entity_id=record.pk,
        library=library,
        changes={"student": str(membership.student_id), "method": "owner"},
    )
    return record


def _locked_record(record_id, *, library) -> AttendanceRecord:
    try:
        return (
            AttendanceRecord.objects.select_for_update(of=("self",))
            .select_related("student", "seat", "library")
            .get(pk=record_id, library=library)
        )
    except (AttendanceRecord.DoesNotExist, ValueError, TypeError):
        raise NotFound() from None


@transaction.atomic
def owner_check_out(*, library, owner, record_id) -> AttendanceRecord:
    """The owner closes an open record by hand (#69)."""
    record = _locked_record(record_id, library=library)
    if record.check_out_at is not None:
        raise ValidationFailed("This student is not checked in.", code="NOT_CHECKED_IN")
    _close(record, at=_after(record), method=AttendanceRecord.Method.OWNER)
    audit.record(
        actor=owner,
        action="attendance.check_out",
        entity_type="attendance_record",
        entity_id=record.pk,
        library=library,
        changes={"student": str(record.student_id), "method": "owner"},
    )
    return record


@transaction.atomic
def correct_record(
    *, library, owner, record_id, reason: str, check_in_at: datetime | None = None, check_out_at: datetime | None = None
) -> AttendanceRecord:
    """Fix the times of a record (#70, ATT-06). Audited with a before/after diff.

    The check-out must come after the check-in and neither may be in the future. Giving a check-out to an open
    record closes it. A check-out cannot be removed.
    """
    record = _locked_record(record_id, library=library)
    now = timezone.now()
    new_in = check_in_at or record.check_in_at
    new_out = check_out_at or record.check_out_at
    if new_in > now or (new_out is not None and new_out > now):
        raise ValidationFailed("Times cannot be in the future.", details={"check_in_at": ["Not in the future."]})
    if new_out is not None and new_out <= new_in:
        raise ValidationFailed("Check-out must be after check-in.", details={"check_out_at": ["After check-in."]})
    before = {"check_in_at": record.check_in_at.isoformat(), "check_out_at": _iso(record.check_out_at)}
    record.check_in_at = new_in
    record.date = timezone.localtime(new_in).date()
    if new_out is not None:
        record.check_out_at = new_out
        record.duration_minutes = _duration(new_in, new_out)
        if record.status == AttendanceRecord.Status.OPEN:
            record.status = AttendanceRecord.Status.CLOSED
            record.check_out_method = AttendanceRecord.Method.OWNER
    record.save()
    audit.record(
        actor=owner,
        action="attendance.correct",
        entity_type="attendance_record",
        entity_id=record.pk,
        library=library,
        changes={"before": before, "after": {"check_in_at": new_in.isoformat(), "check_out_at": _iso(new_out)}},
        reason=reason,
    )
    return record


def _iso(value):
    return value.isoformat() if value else None


def close_for_membership(*, membership: Membership, actor) -> bool:
    """Close the student's open record at this library, called when the membership is archived (#52).

    Runs inside the archive transaction. Returns True if a record was closed.
    """
    record = (
        AttendanceRecord.objects.select_for_update(of=("self",))
        .filter(student_id=membership.student_id, library_id=membership.library_id, check_out_at__isnull=True)
        .first()
    )
    if record is None:
        return False
    _close(record, at=_after(record), method=AttendanceRecord.Method.OWNER)
    audit.record(
        actor=actor,
        action="attendance.check_out",
        entity_type="attendance_record",
        entity_id=record.pk,
        library=membership.library,
        changes={"student": str(record.student_id), "method": "owner", "cause": "membership archived"},
    )
    return True


def closing_time(record: AttendanceRecord) -> datetime:
    """When the record's day ends at its library: `closes_at`, or 23:59 business time if unset (SPEC.md 4.9)."""
    closes = record.library.closes_at or DEFAULT_CLOSING
    naive = datetime.combine(record.date, closes)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def auto_close_open_records(*, now: datetime | None = None) -> dict[str, int]:
    """Close records still open after their library's closing time (the `auto_close_attendance` job step).

    Idempotent: only open records are touched and each is re-read under its row lock.
    """
    now = now or timezone.now()
    open_ids = list(AttendanceRecord.objects.filter(check_out_at__isnull=True).values_list("pk", flat=True))
    closed = 0
    for record_id in open_ids:
        with transaction.atomic():
            record = (
                AttendanceRecord.objects.select_for_update(of=("self",))
                .select_related("library")
                .filter(pk=record_id, check_out_at__isnull=True)
                .first()
            )
            if record is None:
                continue
            closing = closing_time(record)
            if now < closing:
                continue
            at = max(closing, record.check_in_at + timedelta(seconds=1))
            _close(
                record,
                at=at,
                method=AttendanceRecord.Method.AUTO,
                status=AttendanceRecord.Status.AUTO_CLOSED,
            )
            closed += 1
    logger.info(
        "Attendance auto-close", extra={"checked": len(open_ids), "closed": closed, "at": business_now().isoformat()}
    )
    return {"checked": len(open_ids), "closed": closed}
