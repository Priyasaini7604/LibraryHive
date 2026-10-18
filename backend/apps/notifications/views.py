"""Notification centre endpoints #58-#61. Every user (student or owner) sees only their own."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.core.responses import ok

from . import selectors, services
from .serializers import InboxQuery, NotificationSerializer, ReadAllSerializer, UnreadCountSerializer


class InboxView(APIView):
    """#58: the caller's notifications, newest first; `?unread=true` keeps only unread ones."""

    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=[InboxQuery], responses={200: NotificationSerializer(many=True)})
    def get(self, request):
        query = InboxQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(
            selectors.inbox(request.user, unread_only=query.validated_data["unread"]), request
        )
        return paginator.get_paginated_response(NotificationSerializer(page, many=True).data)


class UnreadCountView(APIView):
    """#59: the badge number."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UnreadCountSerializer})
    def get(self, request):
        return ok({"count": selectors.unread_count(request.user)})


class MarkReadView(APIView):
    """#60: mark one notification read. Idempotent; someone else's id is a 404."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: NotificationSerializer})
    def post(self, request, notification_id):
        notification = services.mark_read(user=request.user, notification_id=notification_id)
        return ok(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    """#61: mark all of the caller's notifications read."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ReadAllSerializer})
    def post(self, request):
        return ok({"updated": services.mark_all_read(user=request.user)})
