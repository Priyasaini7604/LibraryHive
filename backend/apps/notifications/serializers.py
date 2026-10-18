from rest_framework import serializers

from .models import Notification


class InboxQuery(serializers.Serializer):
    unread = serializers.BooleanField(required=False, default=False)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "entity_type", "entity_id", "created_at", "read_at"]
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
