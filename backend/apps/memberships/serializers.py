"""Input validation and output shapes for memberships (BACKEND_ARCHITECTURE.md 9.8). No side effects here."""

from decimal import Decimal

from rest_framework import serializers

from apps.accounts.phone import mask_email, mask_phone
from apps.payments.models import Payment

from . import selectors
from .models import Membership

OFFLINE_METHODS = [Payment.Method.CASH, Payment.Method.UPI_DIRECT, Payment.Method.BANK_TRANSFER]
OFFLINE_METHOD_CHOICES = [(m.value, m.label) for m in OFFLINE_METHODS]


# --- Input -------------------------------------------------------------------------------------------------


class OfflinePaymentInput(serializers.Serializer):
    method = serializers.ChoiceField(choices=OFFLINE_METHOD_CHOICES)
    paid_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class RenewalInput(serializers.Serializer):
    """#48. The amount is never accepted: it is the plan price."""

    method = serializers.ChoiceField(choices=OFFLINE_METHOD_CHOICES)
    plan_id = serializers.UUIDField(required=False)
    paid_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class LookupInput(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)


class AdmissionStudentInput(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=120)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    domain_code = serializers.CharField(max_length=40, required=False, allow_blank=True, allow_null=True)


class AdmissionInput(serializers.Serializer):
    student = AdmissionStudentInput()
    seat_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    start_date = serializers.DateField(required=False)
    payment = OfflinePaymentInput()


class ArchiveInput(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300)


class MemberQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=["active", "due", "overdue", "archived", "current"], required=False)
    domain = serializers.CharField(max_length=40, required=False, allow_blank=True)
    source = serializers.ChoiceField(choices=Membership.Source.choices, required=False)
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)


class DuesQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=["due", "overdue"], required=False)
    bucket = serializers.ChoiceField(choices=list(selectors.DUE_BUCKETS), required=False)


class StudentMembershipQuery(serializers.Serializer):
    include_archived = serializers.BooleanField(required=False, default=False)


# --- Output ------------------------------------------------------------------------------------------------


def student_summary(student) -> dict:
    return {
        "id": str(student.pk),
        "name": student.name,
        "phone": student.phone,
        "email": student.email,
        "domain": student.domain.name if student.domain else None,
        "is_offline": student.is_offline,
    }


def masked_student(student, *, is_member_here: bool) -> dict:
    return {
        "id": str(student.pk),
        "name": student.name,
        "masked_phone": mask_phone(student.phone),
        "masked_email": mask_email(student.email),
        "is_offline": student.is_offline,
        "is_member_here": is_member_here,
    }


def payment_row(payment: Payment) -> dict:
    return {
        "id": str(payment.pk),
        "receipt_number": payment.receipt_number,
        "purpose": payment.purpose,
        "channel": payment.channel,
        "method": payment.method,
        "amount": str(payment.amount),
        "plan": payment.plan.name,
        "period_start": payment.period_start,
        "period_end": payment.period_end,
        "paid_at": payment.paid_at,
    }


def membership_core(membership: Membership) -> dict:
    """Owner-side membership shape; `membership.status` must be annotated (selectors._with_status)."""
    return {
        "membership_id": str(membership.pk),
        "seat": {"id": str(membership.seat_id), "label": membership.seat.label},
        "plan": {"id": str(membership.plan_id), "name": membership.plan.name},
        "source": membership.source,
        "status": membership.status,
        "start_date": membership.start_date,
        "next_due_date": membership.next_due_date,
    }


def member_row(membership: Membership) -> dict:
    return {**membership_core(membership), "student": student_summary(membership.student)}


def member_detail(membership: Membership, payments, others, *, attendance_summary: dict, complaints_count: int) -> dict:
    return {
        **member_row(membership),
        "archived_at": membership.archived_at,
        "archive_reason": membership.archive_reason,
        "attendance_summary": attendance_summary,
        "complaints_count": complaints_count,
        "payments": [payment_row(p) for p in payments],
        "other_memberships_here": [membership_core(m) for m in others],
    }


def due_row(membership: Membership) -> dict:
    overdue = selectors.days_overdue(membership)
    return {
        "membership_id": str(membership.pk),
        "student": {"name": membership.student.name, "phone": membership.student.phone},
        "seat_label": membership.seat.label,
        "plan": {"id": str(membership.plan_id), "name": membership.plan.name, "price": str(membership.plan.price)},
        "status": membership.status,
        "next_due_date": membership.next_due_date,
        "days_overdue": overdue,
        "amount_due": str(selectors.amount_due(membership).quantize(Decimal("0.01"))),
    }


def student_membership_row(membership: Membership) -> dict:
    from apps.core.dates import business_today

    plan = membership.plan
    return {
        "id": str(membership.pk),
        "library": {"id": str(membership.library_id), "name": membership.library.name},
        "seat": {"label": membership.seat.label},
        "plan": {"id": str(plan.pk), "name": plan.name, "price": str(plan.price), "duration_days": plan.duration_days},
        "source": membership.source,
        "status": membership.status,
        "start_date": membership.start_date,
        "next_due_date": membership.next_due_date,
        "days_to_due": (membership.next_due_date - business_today()).days,
        "renewal_open": selectors.renewal_open(membership),
    }


def student_membership_detail(membership: Membership, payments) -> dict:
    return {**student_membership_row(membership), "payments": [payment_row(p) for p in payments]}
