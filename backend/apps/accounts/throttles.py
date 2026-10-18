"""Throttles for auth endpoints (BACKEND_ARCHITECTURE.md 4.5)."""

from rest_framework.throttling import SimpleRateThrottle

from .models import normalize_email_address
from .phone import InvalidPhone, normalize_phone


class LoginEmailThrottle(SimpleRateThrottle):
    """Limit login attempts per target email (20/hour), on top of the per-IP limit."""

    scope = "login_email"

    def get_cache_key(self, request, view):
        email = normalize_email_address(request.data.get("email") if hasattr(request, "data") else None)
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class _MinuteWindowThrottle(SimpleRateThrottle):
    """Base for limits like "3/10min" (DRF rates cannot express a 10-minute window)."""

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        count, period = rate.split("/")
        if period.endswith("min"):
            return (int(count), int(period[:-3] or 1) * 60)
        return super().parse_rate(rate)


class PasswordResetEmailThrottle(_MinuteWindowThrottle):
    """3 reset requests per 10 minutes per email (BACKEND_ARCHITECTURE.md 4.5).

    Keyed on the submitted email whether or not an account exists, so hitting
    the limit reveals nothing.
    """

    scope = "password_reset_email"

    def get_cache_key(self, request, view):
        email = normalize_email_address(request.data.get("email") if hasattr(request, "data") else None)
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class ClaimStartIdentityThrottle(_MinuteWindowThrottle):
    """3 claim starts per 10 minutes per phone (BACKEND_ARCHITECTURE.md 4.5).

    Keyed on the submitted phone whether or not a record exists, so hitting
    the limit reveals nothing.
    """

    scope = "claim_start_identity"

    def get_cache_key(self, request, view):
        raw = request.data.get("phone") if hasattr(request, "data") else None
        if not isinstance(raw, str):
            return None
        try:
            ident = normalize_phone(raw)
        except InvalidPhone:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}
