"""Throttles for auth endpoints (BACKEND_ARCHITECTURE.md 4.5)."""

from rest_framework.throttling import SimpleRateThrottle

from .models import normalize_email_address


class LoginEmailThrottle(SimpleRateThrottle):
    """Limit login attempts per target email (20/hour), on top of the per-IP limit."""

    scope = "login_email"

    def get_cache_key(self, request, view):
        email = normalize_email_address(request.data.get("email") if hasattr(request, "data") else None)
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}
