"""Standard response envelope (AGENTS.md 2.2, BACKEND_ARCHITECTURE.md 4.1)."""

from typing import Any

from rest_framework import status as http_status
from rest_framework.response import Response

from .context import get_request_id


def envelope(
    *, success: bool, data: Any = None, error: str | None = None, error_code: str | None = None, details: Any = None
) -> dict:
    return {
        "success": success,
        "data": data,
        "error": error,
        "error_code": error_code,
        "details": details,
        "request_id": get_request_id(),
    }


def ok(data: Any = None, status: int = http_status.HTTP_200_OK, headers: dict | None = None) -> Response:
    return Response(envelope(success=True, data=data), status=status, headers=headers)


def created(data: Any = None, headers: dict | None = None) -> Response:
    return ok(data, status=http_status.HTTP_201_CREATED, headers=headers)


def error_response(
    *, status: int, code: str, message: str, details: Any = None, headers: dict | None = None
) -> Response:
    return Response(
        envelope(success=False, error=message, error_code=code, details=details),
        status=status,
        headers=headers,
    )
