"""Input validation and output shapes for direct UPI payments. No side effects here."""

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.core.storage import PRIVATE_FILE_SECONDS, private_file_url

from .models import LibraryPaymentSettings, UpiPaymentRequest


class PaymentSettingsInput(serializers.Serializer):
    upi_enabled = serializers.BooleanField(required=False)
    upi_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    instructions = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class QrUploadInput(serializers.Serializer):
    image = serializers.FileField()


class SubmitInput(serializers.Serializer):
    """Either `hold_id` (new booking) or `membership_id` with an optional `plan_id` (renewal).

    There is deliberately no amount, library, student or status field: they come from the database.
    """

    hold_id = serializers.UUIDField(required=False)
    membership_id = serializers.UUIDField(required=False)
    plan_id = serializers.UUIDField(required=False, allow_null=True)
    utr = serializers.CharField(max_length=60)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    screenshot = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        if bool(attrs.get("hold_id")) == bool(attrs.get("membership_id")):
            raise serializers.ValidationError("Send either hold_id or membership_id.")
        if attrs.get("hold_id"):
            attrs["plan_id"] = None
        return attrs


class DecisionStatusQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=UpiPaymentRequest.Status.choices, required=False)


class RejectInput(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class ApproveInput(serializers.Serializer):
    """`seat_id` is only for the 'seat taken, use another seat' resolution; the server re-checks it."""

    seat_id = serializers.UUIDField(required=False, allow_null=True)


def settings_data(row: LibraryPaymentSettings | None, *, request=None) -> dict:
    """The owner's own settings. The QR link is a short-lived signed link, never a stored URL."""
    if row is None:
        return {"upi_enabled": False, "upi_id": "", "instructions": "", "has_qr": False, "qr_url": None}
    return {
        "upi_enabled": row.upi_enabled,
        "upi_id": row.upi_id,
        "instructions": row.instructions,
        "has_qr": bool(row.qr_key),
        "qr_url": private_file_url(row.qr_key, request=request) if row.qr_key else None,
        "qr_url_expires_in": PRIVATE_FILE_SECONDS if row.qr_key else None,
    }


def payment_info_data(library, row: LibraryPaymentSettings, *, request=None) -> dict:
    """What a paying student sees. Never includes anything about other students."""
    return {
        "library": {
            "id": str(library.pk),
            "name": library.name,
            "contact_phone": library.contact_phone,
            "contact_email": library.contact_email,
        },
        "upi_id": row.upi_id,
        "instructions": row.instructions,
        "qr_url": private_file_url(row.qr_key, request=request) if row.qr_key else None,
        "qr_url_expires_in": PRIVATE_FILE_SECONDS if row.qr_key else None,
    }


def _waiting(req: UpiPaymentRequest) -> dict:
    """How long a pending request has waited, and whether it is past the review target. Nothing is decided."""
    if req.status != UpiPaymentRequest.Status.PENDING:
        return {"waiting_hours": None, "overdue": False}
    hours = int((timezone.now() - req.created_at).total_seconds() // 3600)
    return {"waiting_hours": hours, "overdue": hours >= settings.UPI_REVIEW_TARGET_HOURS}


def _base(req: UpiPaymentRequest) -> dict:
    return {
        **_waiting(req),
        "id": str(req.pk),
        "status": req.status,
        "purpose": req.purpose,
        "amount": str(req.amount),
        "utr": req.utr,
        "student_note": req.student_note,
        "has_screenshot": bool(req.screenshot_key),
        "plan": {"id": str(req.plan_id), "name": req.plan.name, "duration_days": req.plan.duration_days},
        "seat": {"id": str(req.seat_id), "label": req.seat.label} if req.seat_id else None,
        "created_at": req.created_at,
        "reviewed_at": req.reviewed_at,
        "review_note": req.review_note,
        "receipt_number": req.payment.receipt_number if req.payment_id else None,
    }


def student_request_data(req: UpiPaymentRequest) -> dict:
    """The student's view: their own request and how to reach the library, nothing about other students."""
    library = req.library
    return {
        **_base(req),
        "library": {
            "id": str(library.pk),
            "name": library.name,
            "contact_phone": library.contact_phone,
            "contact_email": library.contact_email,
        },
        "can_cancel": req.status == UpiPaymentRequest.Status.PENDING,
    }


def owner_request_data(req: UpiPaymentRequest) -> dict:
    """The owner's view: who paid, so they can match it to their UPI or bank history."""
    student = req.student
    return {
        **_base(req),
        "student": {"id": str(student.pk), "name": student.name, "phone": student.phone},
        "reviewed_by": req.reviewed_by.name if req.reviewed_by_id else None,
    }
