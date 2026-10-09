"""JWT issuing, rotation and revocation (SECURITY.md section 4).

Claims: user_id (SimpleJWT default), role and name. The role claim is a UI
hint only; permissions always use the user row from the database.
"""

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.exceptions import AppError


class TokenInvalid(AppError):
    status = 401
    code = "TOKEN_INVALID"
    message = "Your session has expired. Please log in again."


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str


def issue_tokens(user) -> TokenPair:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["name"] = user.name
    return TokenPair(access=str(refresh.access_token), refresh=str(refresh))


def rotate(refresh_token: str | None) -> TokenPair:
    """Exchange a refresh token for a new pair; the old one is blacklisted."""
    if not refresh_token:
        raise TokenInvalid()
    serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
    try:
        serializer.is_valid(raise_exception=True)
    except (TokenError, AuthenticationFailed, ValidationError, get_user_model().DoesNotExist):
        # Expired, malformed, blacklisted, or the user is inactive.
        raise TokenInvalid() from None
    return TokenPair(access=serializer.validated_data["access"], refresh=serializer.validated_data["refresh"])


def revoke(refresh_token: str | None, *, user=None) -> None:
    """Blacklist one refresh token. Idempotent; invalid tokens are ignored."""
    if not refresh_token:
        return
    try:
        token = RefreshToken(refresh_token)
    except TokenError:
        return
    if user is not None and str(token.get("user_id")) != str(user.pk):
        return
    token.blacklist()


def revoke_all(user) -> int:
    """Blacklist every outstanding refresh token of a user (e.g. after a password reset)."""
    revoked = 0
    for outstanding in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=outstanding)
        revoked += int(created)
    return revoked
