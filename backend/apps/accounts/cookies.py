"""Refresh-token cookie and CSRF protection for the cookie endpoints (SEC-1, SECURITY.md 4.2-4.3).

The refresh token never appears in JSON. It lives in an HttpOnly, Secure,
SameSite=Strict cookie scoped to /api/v1/auth/, reached through the
frontend's same-site rewrite. Endpoints that read or set it require a JSON
request (JsonRequestRequired) and an Origin header equal to FRONTEND_URL
(FrontendOriginRequired).
"""

import logging
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.permissions import BasePermission

from apps.core.exceptions import AppError, Forbidden

security_logger = logging.getLogger("apps.security")


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict")


def read_refresh_cookie(request) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE_NAME) or None


class UnsupportedMediaType(AppError):
    status = 415
    code = "UNSUPPORTED_MEDIA_TYPE"
    message = "Requests to this endpoint must be JSON."


class JsonRequestRequired(BasePermission):
    """Cookie endpoints accept only JSON, which a cross-site HTML form cannot send (SECURITY.md 4.3)."""

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if (request.content_type or "").split(";")[0].strip().lower() == "application/json":
            return True
        raise UnsupportedMediaType()


class FrontendOriginRequired(BasePermission):
    """Reject cookie-endpoint requests whose Origin is not the frontend (CSRF defence)."""

    def has_permission(self, request, view):
        origin = request.META.get("HTTP_ORIGIN", "")
        if origin and _origin(origin) == _origin(settings.FRONTEND_URL):
            return True
        security_logger.warning("security.origin_rejected", extra={"origin": origin, "path": request.path})
        raise Forbidden("Request origin not allowed.", code="ORIGIN_NOT_ALLOWED")
