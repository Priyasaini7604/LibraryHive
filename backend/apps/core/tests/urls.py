"""Test-only URLs used to exercise the exception handler and envelope.

Mounted only through @override_settings(ROOT_URLCONF=...) inside tests; never
part of the product URL configuration.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import include, path
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import Conflict
from apps.core.permissions import IsOwner
from apps.core.responses import ok


class OnePerMinute(AnonRateThrottle):
    scope = "test_one_per_minute"
    rate = "1/min"


class _Input(serializers.Serializer):
    name = serializers.CharField(max_length=5)


class OkView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return ok({"hello": "world"})


class ValidationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        _Input(data=request.data).is_valid(raise_exception=True)
        return ok()


class ConflictView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise Conflict("Seat is no longer available.", code="SEAT_UNAVAILABLE")


class AuthRequiredView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return ok()


class OwnerOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request):
        return ok()


class ThrottledView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OnePerMinute]

    def get(self, request):
        return ok()


class CrashView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise RuntimeError("secret internal detail: password=hunter2")


class DuplicateEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        User = get_user_model()
        # The second insert violates user_email_unique, as a race would.
        with transaction.atomic():
            User.objects.create_user(email="dup@example.com", name="A", password="x" * 12, phone="+919811111111")
            User.objects.create_user(email="dup@example.com", name="B", password="x" * 12, phone="+919822222222")
        return ok()


test_patterns = [
    path("ok/", OkView.as_view()),
    path("validation/", ValidationView.as_view()),
    path("conflict/", ConflictView.as_view()),
    path("auth-required/", AuthRequiredView.as_view()),
    path("owner-only/", OwnerOnlyView.as_view()),
    path("throttled/", ThrottledView.as_view()),
    path("crash/", CrashView.as_view()),
    path("duplicate-email/", DuplicateEmailView.as_view()),
]

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/_test/", include(test_patterns)),
]

handler404 = "apps.core.views.json_not_found"
handler500 = "apps.core.views.json_server_error"
