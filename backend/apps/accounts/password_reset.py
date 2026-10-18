"""Forgot / reset password (AUTH-15, BACKEND_ARCHITECTURE.md #13a and #13b, SECURITY.md section 3).

Security properties implemented here:
- The request endpoint answers identically whether or not an account exists
  (same status, same body, padded to a minimum duration, and no email for
  unknown, offline or deactivated accounts).
- Codes are 6 random digits, stored hashed with Django's password hasher,
  valid for PASSWORD_RESET_MINUTES, single use, and limited to
  CLAIM_MAX_ATTEMPTS wrong tries. A new request revokes the previous code.
- Wrong-code attempts are also counted per email in the cache for emails
  with no account, so lock-out (429) never reveals that an account exists.
- A successful reset blacklists every outstanding refresh token and writes
  an audit row. The code is only consumed when the new password is accepted.
"""

import hashlib
import logging
import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import AppError, ValidationFailed

from .models import AccountClaim, User, normalize_email_address
from .tokens import revoke_all

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("apps.security")

REQUEST_MESSAGE = "If an account exists for that email, we've sent a reset code."
CONFIRM_MESSAGE = "Your password has been changed. Please log in."

# Hash checked when no real claim exists, so the "no code pending" path costs the same time.
_DUMMY_HASH = make_password("000000")


class ResetInvalid(AppError):
    status = 400
    code = "RESET_INVALID"
    message = "That code is wrong or has expired."


class ResetLocked(AppError):
    status = 429
    code = "CLAIM_LOCKED"
    message = "Too many attempts. Please wait a few minutes and try again."


def _eligible_user(email: str | None) -> User | None:
    """Only active, online accounts with a usable password can reset (offline records must claim)."""
    if not email:
        return None
    user = User.objects.filter(email=email).first()
    if user is None or not user.is_active or user.is_offline or not user.has_usable_password():
        return None
    return user


def _failure_key(email: str) -> str:
    return "pwreset-fail:" + hashlib.sha256(email.encode()).hexdigest()


def _failures(email: str) -> int:
    return int(cache.get(_failure_key(email), 0))


def _record_failure(email: str) -> int:
    key = _failure_key(email)
    cache.add(key, 0, timeout=settings.PASSWORD_RESET_MINUTES * 60)
    return int(cache.incr(key))


def _clear_failures(email: str) -> None:
    cache.delete(_failure_key(email))


def send_email(template: str, subject: str, user: User, **context) -> bool:
    body = render_to_string(f"accounts/email/{template}.txt", {"name": user.name, **context})
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception:  # delivery failures must never change the API response
        logger.exception("email.failed", extra={"template": template, "recipient_id": str(user.pk)})
        return False
    logger.info("email.sent", extra={"template": template, "recipient_id": str(user.pk)})
    return True


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def pad_to_minimum(started: float) -> None:
    """Make every request take at least the configured time, hiding whether work was done."""
    remaining = settings.PASSWORD_RESET_MIN_RESPONSE_SECONDS - (time.monotonic() - started)
    if remaining > 0:
        time.sleep(remaining)


def request_password_reset(*, email: str) -> str:
    """#13a. Always returns the same message; emails a code only to eligible accounts."""
    started = time.monotonic()
    email = normalize_email_address(email) or ""
    user = _eligible_user(email)
    _clear_failures(email)  # a fresh request starts a fresh attempt budget

    code = None
    if user is not None:
        code = new_code()
        now = timezone.now()
        with transaction.atomic():
            AccountClaim.objects.filter(
                user=user, channel=AccountClaim.Channel.PASSWORD_RESET, status=AccountClaim.Status.PENDING
            ).update(status=AccountClaim.Status.REVOKED)
            AccountClaim.objects.create(
                user=user,
                channel=AccountClaim.Channel.PASSWORD_RESET,
                code_hash=make_password(code),
                expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_MINUTES),
            )
        send_email(
            "password_reset",
            "Your LibraryHive password reset code",
            user,
            code=code,
            minutes=settings.PASSWORD_RESET_MINUTES,
        )
    else:
        make_password("000000")  # comparable hashing cost for unknown accounts

    security_logger.info("auth.password_reset_requested", extra={"email": email, "account_found": user is not None})
    pad_to_minimum(started)
    return REQUEST_MESSAGE


def _pending_claim(user: User | None, claim_id=None) -> AccountClaim | None:
    """The user's pending reset claim, row-locked; optionally that exact claim."""
    if user is None:
        return None
    queryset = AccountClaim.objects.select_for_update().filter(
        user=user, channel=AccountClaim.Channel.PASSWORD_RESET, status=AccountClaim.Status.PENDING
    )
    if claim_id is not None:
        queryset = queryset.filter(pk=claim_id)
    return queryset.first()


def confirm_password_reset(*, email: str, code: str, new_password: str) -> str:
    """#13b. Verify the code, set the new password and sign the user out everywhere."""
    email = normalize_email_address(email) or ""
    max_attempts = settings.CLAIM_MAX_ATTEMPTS

    if _failures(email) >= max_attempts:
        security_logger.warning("auth.password_reset_failed", extra={"email": email, "reason": "locked"})
        raise ResetLocked()

    user = _eligible_user(email)

    with transaction.atomic():
        claim = _pending_claim(user)
        valid = False
        verified_claim_id = None
        if claim is not None and claim.expires_at <= timezone.now():
            claim.status = AccountClaim.Status.EXPIRED
            claim.save(update_fields=["status", "updated_at"])
            claim = None
        if claim is not None:
            valid = check_password(code, claim.code_hash)
            verified_claim_id = claim.pk if valid else None
        else:
            check_password(code, _DUMMY_HASH)  # same cost as a real check

        if not valid:
            failures = _record_failure(email)
            if claim is not None:
                claim.attempts += 1
                if claim.attempts >= max_attempts:
                    claim.status = AccountClaim.Status.REVOKED
                claim.save(update_fields=["attempts", "status", "updated_at"])
            security_logger.warning(
                "auth.password_reset_failed", extra={"email": email, "reason": "invalid", "attempt": failures}
            )
            # The failed-attempt bookkeeping above must be committed, so signal after the block.
            locked = failures >= max_attempts
        else:
            locked = False

    if not valid:
        raise ResetLocked() if locked else ResetInvalid()

    # Correct code: validate the password before consuming it so a weak password can be retried.
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationFailed(details={"new_password": list(exc.messages)}) from None

    with transaction.atomic():
        claim = _pending_claim(user, verified_claim_id)
        if claim is None:  # consumed or replaced by a concurrent request between the two checks
            raise ResetInvalid()
        claim.status = AccountClaim.Status.USED
        claim.used_at = timezone.now()
        claim.save(update_fields=["status", "used_at", "updated_at"])
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        revoked = revoke_all(user)
        audit.record(
            actor=user,
            action="account.password_reset",
            entity_type="user",
            entity_id=user.pk,
            reason="Password reset with an emailed code",
            changes={"sessions_revoked": [None, revoked]},
        )

    _clear_failures(email)
    security_logger.info("auth.password_reset_completed", extra={"reset_user_id": str(user.pk), "sessions": revoked})
    send_email("password_changed", "Your LibraryHive password was changed", user)
    return CONFIRM_MESSAGE
