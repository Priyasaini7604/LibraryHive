"""Request ID and access-log middleware (BACKEND_ARCHITECTURE.md 14.1)."""

import logging
import re
import time
import uuid

from .context import client_ip_var, library_id_var, request_id_var, set_user_context, user_id_var

access_logger = logging.getLogger("apps.http")

# Accept a caller-supplied request ID only if it is short and harmless.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestIdMiddleware:
    """Assigns a request ID, exposes it as X-Request-ID and resets log context."""

    header = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.header, "")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        tokens = [
            request_id_var.set(request_id),
            user_id_var.set(None),
            library_id_var.set(None),
            # REMOTE_ADDR only; trusted proxy handling is configured per host (SECURITY.md 12).
            client_ip_var.set(request.META.get("REMOTE_ADDR")),
        ]
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            for var, token in zip((request_id_var, user_id_var, library_id_var, client_ip_var), tokens, strict=True):
                var.reset(token)


class AccessLogMiddleware:
    """Logs one line per request: method, path, status and duration."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        if user_id_var.get() is None:
            # DRF stores the authenticated user on the underlying HttpRequest.
            set_user_context(getattr(request, "user", None))
        access_logger.info(
            "http.request",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "user_id": user_id_var.get(),
                "library_id": library_id_var.get(),
            },
        )
        return response
