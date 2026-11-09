"""Query validation and output shapes for dashboards and reports. No side effects here."""

from datetime import timedelta

from rest_framework import serializers

from . import platform_selectors
from .selectors import MAX_REVENUE_DAYS


class _FromTo(serializers.Serializer):
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)

    def to_internal_value(self, data):
        data = {("from_" if key == "from" else key): value for key, value in data.items()}
        return super().to_internal_value(data)

    def validate(self, attrs):
        start, end = attrs.get("from_"), attrs.get("to")
        if start and end and end < start:
            raise serializers.ValidationError({"to": ["Must not be before the start date."]})
        return attrs


class RevenueQuery(_FromTo):
    """`from` and `to` are required here; a range is at most 366 days (#84)."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "from_" not in attrs or "to" not in attrs:
            raise serializers.ValidationError("Send both from and to.")
        if attrs["to"] - attrs["from_"] > timedelta(days=MAX_REVENUE_DAYS - 1):
            raise serializers.ValidationError("Choose a range of at most 366 days.")
        return attrs


class OptionalRangeQuery(_FromTo):
    pass


class MemberExportQuery(_FromTo):
    status = serializers.ChoiceField(choices=["active", "due", "overdue", "archived"], required=False)


class AuditQuery(_FromTo):
    action = serializers.CharField(max_length=60, required=False)
    entity_type = serializers.CharField(max_length=40, required=False)


def audit_row(entry) -> dict:
    actor = entry.actor
    return {
        "id": str(entry.pk),
        "created_at": entry.created_at,
        "actor": {"name": actor.name if actor else "System", "role": entry.actor_role},
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": str(entry.entity_id),
        "changes": entry.changes,
        "reason": entry.reason,
    }


def _plain_visit(visit) -> dict:
    return {
        "id": str(visit.pk),
        "library": {"id": str(visit.library_id), "name": visit.library.name},
        "preferred_date": visit.preferred_date,
        "preferred_slot": visit.preferred_slot,
        "status": visit.status,
    }


def student_dashboard_data(data: dict) -> dict:
    """Shape the student's home (#89) from the selector's objects."""
    from apps.attendance.serializers import record_row
    from apps.memberships.serializers import student_membership_row
    from apps.payments.serializers import PaymentSerializer

    hold = data["pending_hold"]
    attendance = data["current_attendance"]
    return {
        "memberships": [student_membership_row(m) for m in data["memberships"]],
        "current_attendance": record_row(attendance) if attendance else None,
        "recent_payments": PaymentSerializer(data["recent_payments"], many=True).data,
        "open_complaints": data["open_complaints"],
        "visits": [_plain_visit(v) for v in data["visits"]],
        "pending_hold": None
        if hold is None
        else {
            "id": str(hold.pk),
            "library": {"id": str(hold.library_id), "name": hold.library.name},
            "seat_label": hold.seat.label,
            "plan": {"id": str(hold.plan_id), "name": hold.plan.name},
            "expires_at": hold.expires_at,
        },
    }


class PlatformRangeQuery(_FromTo):
    """Date range for the internal dashboard: defaults to the last 30 days, at most 366 days."""

    granularity = serializers.ChoiceField(choices=platform_selectors.GRANULARITIES, required=False, default="day")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        _, default_end = platform_selectors.default_range()
        end = attrs.get("to") or default_end
        start = attrs.get("from_") or (end - timedelta(days=platform_selectors.DEFAULT_RANGE_DAYS - 1))
        if end < start:
            raise serializers.ValidationError({"to": ["Must not be before the start date."]})
        if end - start > timedelta(days=platform_selectors.MAX_RANGE_DAYS - 1):
            raise serializers.ValidationError("Choose a range of at most 366 days.")
        attrs["from_"], attrs["to"] = start, end
        return attrs


class PlatformLibrariesQuery(PlatformRangeQuery):
    search = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    ordering = serializers.CharField(required=False, default="-bookings")

    def validate_ordering(self, value):
        if value.lstrip("-") not in platform_selectors.LIBRARY_ORDERINGS:
            raise serializers.ValidationError("Unknown ordering.")
        return value
