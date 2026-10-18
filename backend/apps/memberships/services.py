"""Membership state changes (BACKEND_ARCHITECTURE.md section 8).

Only what T14 needs lives here so far: turning a paid booking hold into the active membership. Admission,
renewal and archival (T15) are added to this module by that task.
"""

import logging
from datetime import date, timedelta

from apps.core import audit

from .models import Membership

logger = logging.getLogger("apps.memberships")


def activate_from_hold(*, hold, start_date: date) -> Membership:
    """Create the active online membership a verified payment pays for (SPEC.md 4.3, BOOK-06).

    The caller (payments.confirm_payment) already holds the seat row lock and has checked that the seat and
    the student are free, inside one transaction. If a race still slips through, the partial uniques
    (`membership_one_live_per_seat`, `membership_one_live_per_student_library`) raise IntegrityError and the
    caller treats the seat as lost.

    The period is the plan's duration from `start_date`; the amount and duration come from the plan row, never
    from the request.
    """
    plan = hold.plan
    membership = Membership.objects.create(
        student=hold.student,
        library=hold.library,
        seat=hold.seat,
        plan=plan,
        source=Membership.Source.ONLINE,
        state=Membership.State.ACTIVE,
        start_date=start_date,
        next_due_date=start_date + timedelta(days=plan.duration_days),
        created_by=hold.student,
    )
    audit.record(
        actor=hold.student,
        action="membership.create",
        entity_type="membership",
        entity_id=membership.pk,
        library=hold.library,
        changes={"seat": hold.seat.label, "plan": plan.name, "source": "online"},
    )
    logger.info(
        "Membership activated from hold",
        extra={"membership_id": str(membership.pk), "hold_id": str(hold.pk), "student_id": str(hold.student_id)},
    )
    return membership
