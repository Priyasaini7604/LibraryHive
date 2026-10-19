"""Input and output shapes for attendance (BACKEND_ARCHITECTURE.md 9.9). No side effects here."""

import re

from rest_framework import serializers

from .models import AttendanceRecord


class CheckInInput(serializers.Serializer):
    library_id = serializers.UUIDField()


class OwnerCheckInInput(serializers.Serializer):
    membership_id = serializers.UUIDField()


class CorrectionInput(serializers.Serializer):
    check_in_at = serializers.DateTimeField(required=False)
    check_out_at = serializers.DateTimeField(required=False)
    reason = serializers.CharField(min_length=3, max_length=300)

    def validate(self, attrs):
        if "check_in_at" not in attrs and "check_out_at" not in attrs:
            raise serializers.ValidationError("Send check_in_at or check_out_at.")
        return attrs


class StudentHistoryQuery(serializers.Serializer):
    month = serializers.CharField(required=False)

    def validate_month(self, value):
        match = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", value)
        if not match:
            raise serializers.ValidationError("Use YYYY-MM.")
        return int(match.group(1)), int(match.group(2))


class OwnerHistoryQuery(serializers.Serializer):
    date = serializers.DateField(required=False)
    # `from` is a Python keyword, so the query names are mapped explicitly.
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)
    student_id = serializers.UUIDField(required=False)

    def to_internal_value(self, data):
        data = {("from_" if key == "from" else key): value for key, value in data.items()}
        return super().to_internal_value(data)


def record_row(record: AttendanceRecord) -> dict:
    return {
        "id": str(record.pk),
        "library": {"id": str(record.library_id), "name": record.library.name},
        "seat_label": record.seat.label if record.seat else None,
        "date": record.date,
        "check_in_at": record.check_in_at,
        "check_out_at": record.check_out_at,
        "duration_minutes": record.duration_minutes,
        "check_in_method": record.check_in_method,
        "check_out_method": record.check_out_method,
        "status": record.status,
    }


def owner_record_row(record: AttendanceRecord) -> dict:
    return {**record_row(record), "student": {"id": str(record.student_id), "name": record.student.name}}


def live_row(record: AttendanceRecord) -> dict:
    return {
        "record_id": str(record.pk),
        "student": {"id": str(record.student_id), "name": record.student.name},
        "seat_label": record.seat.label if record.seat else None,
        "check_in_at": record.check_in_at,
    }
