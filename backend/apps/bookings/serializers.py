from rest_framework import serializers

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id",
            "student",
            "library",
            "seat",
            "plan",
            "status",
            "reserved_until",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "student",
            "status",
            "reserved_until",
            "created_at",
            "updated_at",
        ]