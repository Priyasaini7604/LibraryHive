"""Input validation and output shapes for seats. No side effects here."""

from rest_framework import serializers

from .models import Seat, SeatHold
from .services import MAX_SEATS_PER_REQUEST


class SeatItemInput(serializers.Serializer):
    label = serializers.CharField(min_length=1, max_length=50, trim_whitespace=True)
    row_label = serializers.CharField(max_length=10, required=False, allow_blank=True, trim_whitespace=True)
    position = serializers.IntegerField(min_value=0, max_value=32767, required=False, allow_null=True)


class SeatCreateInput(serializers.Serializer):
    """#31: a grid (rows x seats per row) or an explicit list of at most 500 seats."""

    mode = serializers.ChoiceField(choices=["grid", "list"])
    rows = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=10, trim_whitespace=True),
        required=False,
        min_length=1,
        max_length=100,
    )
    seats_per_row = serializers.IntegerField(min_value=1, max_value=50, required=False)
    seats = SeatItemInput(many=True, required=False, max_length=MAX_SEATS_PER_REQUEST)

    def validate(self, attrs):
        if attrs["mode"] == "grid":
            missing = {key: ["This field is required."] for key in ("rows", "seats_per_row") if key not in attrs}
            if missing:
                raise serializers.ValidationError(missing)
            if len(attrs["rows"]) * attrs["seats_per_row"] > MAX_SEATS_PER_REQUEST:
                raise serializers.ValidationError(
                    {"rows": [f"A grid can create at most {MAX_SEATS_PER_REQUEST} seats at once."]}
                )
        elif "seats" not in attrs:
            raise serializers.ValidationError({"seats": ["This field is required."]})
        return attrs


class SeatUpdateInput(serializers.Serializer):
    label = serializers.CharField(min_length=1, max_length=50, required=False, trim_whitespace=True)
    row_label = serializers.CharField(max_length=10, required=False, allow_blank=True, trim_whitespace=True)
    position = serializers.IntegerField(min_value=0, max_value=32767, required=False, allow_null=True)


class OwnerSeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ["id", "label", "row_label", "position", "is_active", "is_disabled", "disabled_reason"]
        read_only_fields = fields


class ReasonInput(serializers.Serializer):
    """Owner overrides always carry a reason (SEAT-07); it goes to the audit trail."""

    reason = serializers.CharField(min_length=3, max_length=200, trim_whitespace=True)


class CreateHoldInput(serializers.Serializer):
    seat_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()


class StudentHoldSerializer(serializers.ModelSerializer):
    """#38-#40: what the checkout screen needs. Never exposes other students or library internals."""

    seat = serializers.SerializerMethodField()
    library = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = SeatHold
        fields = ["id", "seat", "library", "plan", "amount", "expires_at"]
        read_only_fields = fields

    def get_seat(self, hold) -> dict:
        return {"id": str(hold.seat_id), "label": hold.seat.label}

    def get_library(self, hold) -> dict:
        return {"id": str(hold.library_id), "name": hold.library.name}

    def get_plan(self, hold) -> dict:
        plan = hold.plan
        return {"id": str(plan.pk), "name": plan.name, "duration_days": plan.duration_days, "price": str(plan.price)}

    def get_amount(self, hold) -> str:
        # Always the plan's price from the database: the client never sends an amount.
        return str(hold.plan.price)


class OwnerHoldSerializer(serializers.ModelSerializer):
    seat = serializers.SerializerMethodField()

    class Meta:
        model = SeatHold
        fields = ["id", "kind", "status", "seat", "reason", "expires_at", "created_at"]
        read_only_fields = fields

    def get_seat(self, hold) -> dict:
        return {"id": str(hold.seat_id), "label": hold.seat.label}
