from rest_framework import serializers

from .models import Membership


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = [
            "id",
            "student",
            "library",
            "plan",
            "seat",
            "start_date",
            "next_due_date",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "student",
            "start_date",
            "next_due_date",
            "status",
            "created_at",
            "updated_at",
        ]