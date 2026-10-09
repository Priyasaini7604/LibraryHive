"""Per-request context shared by logging, auditing and the response envelope.

Values are stored in context variables so they are isolated per request (and
per thread or task) without passing the request object around.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
library_id_var: ContextVar[str | None] = ContextVar("library_id", default=None)
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def set_user_context(user) -> None:
    """Record the authenticated user (and their library, for owners) for logs."""
    if user is None or not getattr(user, "is_authenticated", False):
        return
    user_id_var.set(str(user.pk))
    library = getattr(user, "library", None)
    if library is not None:
        library_id_var.set(str(library.pk))
