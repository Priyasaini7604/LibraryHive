"""Audit trail helper (SPEC.md 3.4, BACKEND_ARCHITECTURE.md 14.2).

Call `record()` inside the same `transaction.atomic()` block as the change it
describes, so the audit row commits or rolls back together with the change.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from .context import client_ip_var, get_request_id
from .logging import SENSITIVE_KEYS
from .models import AuditLog


def _actor_role(actor) -> str:
    if actor is None:
        return AuditLog.ActorRole.SYSTEM
    if getattr(actor, "is_staff", False):
        return AuditLog.ActorRole.STAFF
    return actor.role


def changes_between(
    before: dict[str, Any], after: dict[str, Any], fields: Iterable[str] | None = None
) -> dict[str, list[Any]]:
    """Return {field: [old, new]} for fields whose value changed.

    Sensitive fields are never included (SECURITY.md section 16).
    """
    keys = fields if fields is not None else (set(before) | set(after))
    diff: dict[str, list[Any]] = {}
    for key in keys:
        if key.lower() in SENSITIVE_KEYS:
            continue
        old, new = before.get(key), after.get(key)
        if old != new:
            diff[key] = [_jsonable(old), _jsonable(new)]
    return diff


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def record(
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str,
    changes: dict[str, Any] | None = None,
    reason: str = "",
) -> AuditLog:
    """Append one audit row. Never pass secrets in `changes`."""
    safe_changes = {k: v for k, v in (changes or {}).items() if k.lower() not in SENSITIVE_KEYS}
    return AuditLog.objects.create(
        actor=actor,
        actor_role=_actor_role(actor),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=safe_changes,
        reason=reason,
        ip_address=client_ip_var.get(),
        request_id=get_request_id() or "",
    )
