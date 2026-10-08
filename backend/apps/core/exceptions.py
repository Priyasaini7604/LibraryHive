"""Application errors (BACKEND_ARCHITECTURE.md section 6).

Services raise these; the API exception handler turns them into the standard
response envelope. Each error carries an HTTP status, a machine-readable code
and a human-readable message.
"""

from typing import Any


class AppError(Exception):
    status = 400
    code = "BUSINESS_RULE"
    message = "Request could not be completed."

    def __init__(self, message: str | None = None, *, code: str | None = None, details: Any = None):
        self.message = message or self.message
        if code:
            self.code = code
        self.details = details
        super().__init__(self.message)


class ValidationFailed(AppError):
    status = 400
    code = "VALIDATION_ERROR"
    message = "Please correct the highlighted fields."


class NotFound(AppError):
    status = 404
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class Forbidden(AppError):
    status = 403
    code = "FORBIDDEN_ROLE"
    message = "You do not have permission to perform this action."


class Conflict(AppError):
    status = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state."


class PayloadTooLarge(AppError):
    status = 413
    code = "FILE_TOO_LARGE"
    message = "The uploaded file is too large."


class GatewayError(AppError):
    status = 502
    code = "GATEWAY_ERROR"
    message = "The payment provider is temporarily unavailable. Please try again shortly."


# Database constraint name -> (HTTP status, error code, message).
# Apps register their partial-unique constraints so that a race that slips past
# the service checks still produces a clean 409 instead of a 500.
_CONSTRAINT_ERRORS: dict[str, tuple[int, str, str]] = {}


def register_constraint_error(constraint_name: str, *, code: str, message: str, status: int = 409) -> None:
    _CONSTRAINT_ERRORS[constraint_name] = (status, code, message)


def lookup_constraint_error(constraint_name: str | None) -> tuple[int, str, str] | None:
    if not constraint_name:
        return None
    return _CONSTRAINT_ERRORS.get(constraint_name)
