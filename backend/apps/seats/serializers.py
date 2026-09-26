from rest_framework import serializers
from .models import Seat


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ["id", "library", "label", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "library", "created_at", "updated_at"]


class SeatCreateInputSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=50)
    status = serializers.ChoiceField(
        choices=Seat.STATUS_CHOICES,
        default="empty",
        required=False,
    )


class SeatBulkCreateSerializer(serializers.Serializer):
    """
    Accepts either an explicit list of seat labels/statuses or a grid layout specification.
    """
    seats = SeatCreateInputSerializer(many=True, required=False)
    # Optional layout generator
    rows = serializers.ListField(
        child=serializers.CharField(max_length=10),
        required=False,
        help_text="e.g. ['A', 'B', 'C']",
    )
    seats_per_row = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        help_text="Number of seats per row",
    )
