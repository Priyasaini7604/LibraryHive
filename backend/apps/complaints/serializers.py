from rest_framework import serializers
from .models import Complaint


class ComplaintCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ["id", "library", "category", "description", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def create(self, validated_data):
        validated_data["student"] = self.context["request"].user
        return super().create(validated_data)


class ComplaintListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Complaint
        fields = ["id", "student_name", "library", "category", "description",
                  "status", "resolution_note", "created_at", "resolved_at"]


class ComplaintResolveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = ["status", "resolution_note"]