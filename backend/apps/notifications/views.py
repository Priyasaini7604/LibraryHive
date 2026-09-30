from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = (
            Notification.objects
            .filter(recipient=request.user)
            .select_related(
                "library",
                "membership",
            )
        )

        serializer = NotificationSerializer(
            notifications,
            many=True,
        )

        return Response(serializer.data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notification = (
            Notification.objects
            .filter(
                id=notification_id,
                recipient=request.user,
            )
            .select_related(
                "library",
                "membership",
            )
            .first()
        )

        if not notification:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.is_read = True

        notification.save(
            update_fields=[
                "is_read",
                "updated_at",
            ]
        )

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK,
        )