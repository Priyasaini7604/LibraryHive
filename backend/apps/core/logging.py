"""Structured JSON logging with redaction (FEATURES LOG-01..LOG-05, LOG-08).

Usage in any app:

    logger = logging.getLogger(__name__)
    logger.info("hold.created", extra={"seat_id": str(seat.id)})

The message is the event name. Request context (request_id, user_id,
library_id) is added automatically. Sensitive keys are dropped and emails and
phone numbers are masked before anything is written.
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from .context import library_id_var, request_id_var, user_id_var

# Keys whose values must never be logged (SECURITY.md section 16).
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "new_password",
        "token",
        "access",
        "refresh",
        "code",
        "otp",
        "signature",
        "razorpay_signature",
        "secret",
        "authorization",
        "cookie",
        "api_key",
        "key_secret",
    }
)
REDACTED = "[REDACTED]"

_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE = re.compile(r"(?<![\w])(\+?\d{4})\d{4,9}(\d{2})(?!\w)")

# Attributes present on every LogRecord; anything else came from `extra=`.
_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()) | {
    "message",
    "asctime",
    "taskName",
}


def mask_text(value: str) -> str:
    """Mask emails (r***@gmail.com) and phone numbers (+9198******10) in text."""
    value = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", value)
    return _PHONE.sub(lambda m: f"{m.group(1)}******{m.group(2)}", value)


def redact(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if key is not None and (key == "id" or key.endswith("_id")):
        return value  # identifiers (UUIDs, request IDs) are not personal data
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    return {key: value for key, value in vars(record).items() if key not in _STANDARD_ATTRS}


class ContextFilter(logging.Filter):
    """Adds request context to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or request_id_var.get()
        record.user_id = getattr(record, "user_id", None) or user_id_var.get()
        record.library_id = getattr(record, "library_id", None) or library_id_var.get()
        return True


class RedactionFilter(logging.Filter):
    """Drops sensitive keys and masks personal data in messages and extras."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_text(record.msg)
        if record.args:
            record.args = (
                tuple(redact(arg) for arg in record.args) if isinstance(record.args, tuple) else redact(record.args)
            )
        for key, value in _extra_fields(record).items():
            setattr(record, key, redact(value, key))
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": message,
            "request_id": getattr(record, "request_id", None),
            "user_id": getattr(record, "user_id", None),
            "library_id": getattr(record, "library_id", None),
        }
        for key, value in _extra_fields(record).items():
            if key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = mask_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)
