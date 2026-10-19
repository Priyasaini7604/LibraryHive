"""Input and output shapes for visit requests (BACKEND_ARCHITECTURE.md 9.11). No side effects here."""

from rest_framework import serializers

from .models import VisitRequest


class RequestVisitInput(serializers.Serializer):
    library_id = serializers.UUIDField()
    preferred_date = serializers.DateField()
    preferred_slot = serializers.ChoiceField(choices=VisitRequest.Slot.choices)
    student_note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class DecisionInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accept", "reject"])
    owner_note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class StudentQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=VisitRequest.Status.choices, required=False)


class OwnerQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=VisitRequest.Status.choices, required=False)
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)

    def to_internal_value(self, data):
        data = {("from_" if key == "from" else key): value for key, value in data.items()}
        return super().to_internal_value(data)


def student_row(visit: VisitRequest) -> dict:
    return {
        "id": str(visit.pk),
        "library": {"id": str(visit.library_id), "name": visit.library.name},
        "preferred_date": visit.preferred_date,
        "preferred_slot": visit.preferred_slot,
        "student_note": visit.student_note,
        "status": visit.status,
        "owner_note": visit.owner_note,
        "decided_at": visit.decided_at,
        "created_at": visit.created_at,
    }


def owner_row(visit: VisitRequest) -> dict:
    student = visit.student
    return {
        **student_row(visit),
        "student": {"id": str(student.pk), "name": student.name, "phone": student.phone},
    }
