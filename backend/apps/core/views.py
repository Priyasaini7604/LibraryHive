"""Platform endpoints: health (#1), vocabularies (#2, #3), OpenAPI schema (#5)."""

import hmac
import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import FileResponse, Http404, JsonResponse
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import jobs
from .models import Amenity, Domain
from .responses import envelope, error_response, ok
from .serializers import AmenitySerializer, DomainSerializer
from .storage import private_storage, read_private_file_key

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Liveness and database check. Reveals no dependency versions."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(summary="Health check", responses={200: None, 503: None})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            logger.error("health.db_unavailable")
            return error_response(status=503, code="SERVICE_UNAVAILABLE", message="Database unavailable.")
        return ok({"status": "ok", "db": "ok", "version": settings.APP_VERSION})


class DomainListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(summary="Exam domain vocabulary", responses=DomainSerializer(many=True))
    def get(self, request):
        return ok(DomainSerializer(Domain.objects.filter(is_active=True), many=True).data)


class AmenityListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(summary="Amenity vocabulary", responses=AmenitySerializer(many=True))
    def get(self, request):
        return ok(AmenitySerializer(Amenity.objects.filter(is_active=True), many=True).data)


class JobTriggerView(APIView):
    """#4: run the scheduled jobs from outside cron (for hosts without a scheduler).

    Disabled (404) unless `JOB_TRIGGER_TOKEN` is set. The `X-Job-Token` header is compared in constant time;
    no session or JWT is accepted. The jobs are idempotent, so a repeated call is harmless.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "job_trigger"

    @extend_schema(summary="Run the scheduled jobs (token required)", request=None, responses={200: None})
    def post(self, request):
        expected = settings.JOB_TRIGGER_TOKEN
        if not expected:
            return error_response(status=404, code="NOT_FOUND", message="The requested resource was not found.")
        supplied = request.headers.get("X-Job-Token", "")
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            logging.getLogger("apps.security").warning("security.invalid_job_token")
            return error_response(status=403, code="FORBIDDEN_ROLE", message="Invalid job token.")
        return ok(jobs.run_steps())


class SchemaView(SpectacularAPIView):
    """OpenAPI schema: public in local/test, staff-only in production."""

    def get_permissions(self):
        return [AllowAny()] if settings.SCHEMA_PUBLIC else [IsAdminUser()]


def json_not_found(request, exception=None):
    """Django-level 404 (outside DRF views) in the standard envelope."""
    return JsonResponse(
        envelope(success=False, error="The requested resource was not found.", error_code="NOT_FOUND"),
        status=404,
    )


def json_server_error(request):
    """Django-level 500 in the standard envelope; never exposes internals."""
    return JsonResponse(
        envelope(success=False, error="Something went wrong on our side. Please try again.", error_code="SERVER_ERROR"),
        status=500,
    )


class PrivateFileView(APIView):
    """Serves one private image for a signed, expiring link (local filesystem only).

    The link is made by `core.storage.private_file_url`, after the calling view has checked who may see the image.
    With S3-compatible storage the provider serves pre-signed URLs itself, so this endpoint answers 404 there:
    production has exactly one way to reach a private file.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request, token):
        if settings.STORAGE_BACKEND == "s3":
            raise Http404
        key = read_private_file_key(token)
        storage = private_storage()
        if key is None or not storage.exists(key):
            raise Http404
        response = FileResponse(storage.open(key, "rb"), content_type="image/webp")
        response["Cache-Control"] = "private, no-store"
        return response
