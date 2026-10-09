"""DRF exception handler: every error becomes the standard envelope.

BACKEND_ARCHITECTURE.md section 6. Unknown exceptions are logged with a stack
trace and returned as a generic 500 that never leaks internals.
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework.response import Response

from .exceptions import AppError, lookup_constraint_error
from .responses import error_response

logger = logging.getLogger("apps.core.errors")
security_logger = logging.getLogger("apps.security")

GENERIC_SERVER_ERROR = "Something went wrong on our side. Please try again."
VALIDATION_MESSAGE = "Please correct the highlighted fields."


def _plain(detail: Any) -> Any:
    """Convert DRF ErrorDetail structures into plain JSON-serialisable values."""
    if isinstance(detail, dict):
        return {str(key): _plain(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_plain(item) for item in detail]
    return str(detail)


def _constraint_name(exc: IntegrityError) -> str | None:
    cause = getattr(exc, "__cause__", None)
    diag = getattr(cause, "diag", None)
    return getattr(diag, "constraint_name", None)


def exception_handler(exc: Exception, context: dict) -> Response:
    request = context.get("request")
    path = getattr(request, "path", None)

    if isinstance(exc, AppError):
        return error_response(status=exc.status, code=exc.code, message=exc.message, details=exc.details)

    if isinstance(exc, drf.ValidationError):
        details = _plain(exc.detail)
        if not isinstance(details, dict):
            details = {"non_field_errors": details if isinstance(details, list) else [details]}
        return error_response(status=400, code="VALIDATION_ERROR", message=VALIDATION_MESSAGE, details=details)

    if isinstance(exc, drf.NotAuthenticated):
        return error_response(status=401, code="NOT_AUTHENTICATED", message="Please log in to continue.")

    if isinstance(exc, drf.AuthenticationFailed):
        return error_response(
            status=401, code="TOKEN_INVALID", message="Your session has expired. Please log in again."
        )

    if isinstance(exc, (drf.PermissionDenied, DjangoPermissionDenied)):
        security_logger.warning("security.permission_denied", extra={"path": path})
        return error_response(
            status=403, code="FORBIDDEN_ROLE", message="You do not have permission to perform this action."
        )

    if isinstance(exc, (Http404, drf.NotFound)):
        return error_response(status=404, code="NOT_FOUND", message="The requested resource was not found.")

    if isinstance(exc, drf.Throttled):
        security_logger.warning("security.rate_limited", extra={"path": path, "wait": exc.wait})
        headers = {"Retry-After": str(int(exc.wait))} if exc.wait is not None else None
        return error_response(
            status=429,
            code="RATE_LIMITED",
            message="Too many attempts. Please wait a few minutes and try again.",
            headers=headers,
        )

    if isinstance(exc, drf.MethodNotAllowed):
        return error_response(status=405, code="METHOD_NOT_ALLOWED", message="This method is not allowed here.")

    if isinstance(exc, drf.UnsupportedMediaType):
        return error_response(status=415, code="UNSUPPORTED_MEDIA_TYPE", message="Unsupported request content type.")

    if isinstance(exc, drf.ParseError):
        return error_response(status=400, code="PARSE_ERROR", message="The request body could not be read.")

    if isinstance(exc, IntegrityError):
        mapped = lookup_constraint_error(_constraint_name(exc))
        if mapped:
            status, code, message = mapped
            logger.warning("db.constraint_conflict", extra={"error_code": code, "path": path})
            return error_response(status=status, code=code, message=message)

    if isinstance(exc, drf.APIException):
        # Any other DRF exception keeps its status but never its internal text.
        return error_response(
            status=exc.status_code,
            code="BUSINESS_RULE",
            message=GENERIC_SERVER_ERROR if exc.status_code >= 500 else "Request could not be completed.",
        )

    logger.exception("http.error", extra={"path": path})
    return error_response(status=500, code="SERVER_ERROR", message=GENERIC_SERVER_ERROR)
