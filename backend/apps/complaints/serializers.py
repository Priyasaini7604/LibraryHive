"""Input and output shapes for complaints (BACKEND_ARCHITECTURE.md 9.10). No side effects here."""

from rest_framework import serializers

from .models import Complaint


class CreateComplaintInput(serializers.Serializer):
    library_id = serializers.UUIDField()
    category = serializers.ChoiceField(choices=Complaint.Category.choices)
    description = serializers.CharField(min_length=10, max_length=2000, trim_whitespace=True)


class RespondInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=["in_progress", "resolved"], required=False)
    owner_response = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Send status or owner_response.")
        return attrs


class StudentQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=Complaint.Status.choices, required=False)


class OwnerQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=Complaint.Status.choices, required=False)
    category = serializers.ChoiceField(choices=Complaint.Category.choices, required=False)


def student_row(complaint: Complaint) -> dict:
    return {
        "id": str(complaint.pk),
        "library": {"id": str(complaint.library_id), "name": complaint.library.name},
        "category": complaint.category,
        "description": complaint.description,
        "status": complaint.status,
        "owner_response": complaint.owner_response,
        "responded_at": complaint.responded_at,
        "resolved_at": complaint.resolved_at,
        "created_at": complaint.created_at,
    }


def owner_row(complaint: Complaint) -> dict:
    seat = complaint.membership.seat
    return {
        **student_row(complaint),
        "student": {"id": str(complaint.student_id), "name": complaint.student.name},
        "seat_label": seat.label if seat else None,
    }
