"""Claiming an offline account (OFF-04, BACKEND_ARCHITECTURE.md #12 and #13, SPEC.md 4.6, SECURITY.md section 3).

An owner can add a student who has no account yet (an offline user). The
student later proves ownership of that record before it becomes an online
account; it is never linked by phone or email alone.

Security properties implemented here:
- Two proofs: a 6-digit email OTP (sent to the email on the record, 10 min)
  or an 8-character owner code handed over in person (7 days). Both are
  generated with `secrets`, stored hashed, single use, and limited to
  CLAIM_MAX_ATTEMPTS wrong tries.
- Starting a claim answers identically whether or not a record exists
  (except for the "no email on file" hint the student must act on).
- Wrong attempts are also counted per phone in the cache, so the lock-out
  (429) is the same for phones that have no offline record.
- The same `User` row is converted, so every membership, payment and
  attendance row stays attached. Nothing is merged and names are never used.
- The code is consumed only when the new password is accepted, and the claim
  verified is the claim consumed.
"""

import hashlib
import logging
import secrets
import time
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import AppError, Conflict, ValidationFailed

from .models import AccountClaim, User, normalize_email_address
from .password_reset import new_code, pad_to_minimum, send_email
from .phone import InvalidPhone, mask_email, normalize_phone
from .services import AuthResult
from .tokens import issue_tokens

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("apps.security")

OWNER_CODE_LENGTH = 8
# No 0/O, 1/I/L: the code is read aloud or copied from paper.
OWNER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LOCK_SECONDS = 30 * 60
_CLAIM_CHANNELS = (AccountClaim.Channel.EMAIL_OTP, AccountClaim.Channel.OWNER_CODE)
# Hash checked when no real claim exists, so the "nothing pending" path costs the same time.
_DUMMY_HASH = make_password("000000")


class ClaimInvalid(AppError):
    status = 400
    code = "CLAIM_INVALID"
    message = "That code is wrong or has expired."


class ClaimLocked(AppError):
    status = 429
    code = "CLAIM_LOCKED"
    message = "Too many attempts. Please wait a few minutes and try again."


class EmailDeliveryFailed(AppError):
    status = 502
    code = "EMAIL_FAILED"
    message = "We could not send the email right now. Please try again shortly."


def _phone_or_error(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except InvalidPhone as exc:
        raise ValidationFailed(details={"phone": [str(exc)]}) from None


def _claimable_user(phone: str) -> User | None:
    """The active, unclaimed offline record for this phone, if any."""
    user = User.objects.filter(phone=phone, is_offline=True, is_active=True).first()
    return user if user is not None and not user.has_usable_password() else None


def _failure_key(phone: str) -> str:
    return "claim-fail:" + hashlib.sha256(phone.encode()).hexdigest()


def _failures(phone: str) -> int:
    return int(cache.get(_failure_key(phone), 0))


def _record_failure(phone: str) -> int:
    key = _failure_key(phone)
    cache.add(key, 0, timeout=_LOCK_SECONDS)
    return int(cache.incr(key))


def _clear_failures(phone: str) -> None:
    cache.delete(_failure_key(phone))


def _normalize_code(code: str) -> str:
    return "".join(code.split()).replace("-", "").upper()


def _new_owner_code() -> str:
    return "".join(secrets.choice(OWNER_CODE_ALPHABET) for _ in range(OWNER_CODE_LENGTH))


def _issue_claim(
    user: User, channel: str, code: str, lifetime: timedelta, issued_by: User | None = None
) -> AccountClaim:
    """Revoke the previous pending code for this channel and create the new one (one pending per channel)."""
    with transaction.atomic():
        AccountClaim.objects.filter(user=user, channel=channel, status=AccountClaim.Status.PENDING).update(
            status=AccountClaim.Status.REVOKED
        )
        return AccountClaim.objects.create(
            user=user,
            channel=channel,
            code_hash=make_password(code),
            issued_by=issued_by,
            expires_at=timezone.now() + lifetime,
        )


def start_claim(*, phone: str, channel: str, email: str | None = None) -> dict:
    """#12. Email an OTP when the record qualifies; always answer the same way.

    `masked_email` echoes the email the caller typed, never the one on file,
    so the body does not depend on whether a record exists.
    """
    started = time.monotonic()
    phone = _phone_or_error(phone)
    email = normalize_email_address(email)
    user = _claimable_user(phone)
    matched = user is not None and (email is None or user.email == email)

    if channel == AccountClaim.Channel.EMAIL_OTP and matched:
        if not user.email:
            raise ClaimInvalid(
                "There is no email on file for this record. Ask your library for a claim code instead.",
            )
        code = new_code()
        _issue_claim(user, AccountClaim.Channel.EMAIL_OTP, code, timedelta(minutes=settings.CLAIM_OTP_MINUTES))
        _clear_failures(phone)  # a fresh code starts a fresh attempt budget
        sent = send_email(
            "claim_otp",
            "Your LibraryHive account code",
            user,
            code=code,
            minutes=settings.CLAIM_OTP_MINUTES,
        )
        if not sent:
            raise EmailDeliveryFailed()
    else:
        make_password("000000")  # comparable hashing cost when nothing is sent

    security_logger.info("claim.started", extra={"phone_tail": phone[-4:], "channel": channel, "match": matched})
    pad_to_minimum(started)
    return {"channel": channel, "masked_email": mask_email(email)}


def issue_claim_code(*, student: User, issued_by: User) -> tuple[str, AccountClaim]:
    """Create an owner code for an offline student; the plain code is returned once and never stored.

    The caller (endpoint #55, T06b) is responsible for checking that the
    student has a membership in the owner's library.
    """
    if issued_by.role != User.Role.OWNER:
        raise AppError("Only a library owner can issue a claim code.", code="FORBIDDEN_ROLE")
    code = _new_owner_code()
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=student.pk)
        if not locked.is_offline or locked.has_usable_password():
            raise Conflict("This student has already claimed their account.")
        claim = _issue_claim(
            locked,
            AccountClaim.Channel.OWNER_CODE,
            code,
            timedelta(days=settings.CLAIM_CODE_DAYS),
            issued_by=issued_by,
        )
        audit.record(
            actor=issued_by,
            action="claim.code_issued",
            entity_type="user",
            entity_id=locked.pk,
            changes={"expires_at": [None, claim.expires_at.isoformat()]},
        )
    if student.phone:
        _clear_failures(student.phone)
    return code, claim


def _verify(user: User | None, phone: str, code: str, email: str | None) -> uuid.UUID:
    """Check the code against the user's pending claims. Returns the matching claim id or raises.

    Failure bookkeeping is committed before the error is raised.
    """
    max_attempts = settings.CLAIM_MAX_ATTEMPTS
    with transaction.atomic():
        claims = []
        if user is not None:
            claims = list(
                AccountClaim.objects.select_for_update().filter(
                    user=user, channel__in=_CLAIM_CHANNELS, status=AccountClaim.Status.PENDING
                )
            )
        now = timezone.now()
        live = []
        for claim in claims:
            if claim.expires_at <= now:
                claim.status = AccountClaim.Status.EXPIRED
                claim.save(update_fields=["status", "updated_at"])
            else:
                live.append(claim)

        email_ok = user is not None and (email is None or not user.email or user.email == email)
        matched = None
        if live:
            for claim in live:
                # Check every live claim so timing does not reveal which channel matched.
                if check_password(code, claim.code_hash) and email_ok and matched is None:
                    matched = claim
        else:
            check_password(code, _DUMMY_HASH)  # same cost as a real check

        if matched is not None:
            return matched.pk

        failures = _record_failure(phone)
        for claim in live:
            claim.attempts += 1
            if claim.attempts >= max_attempts:
                claim.status = AccountClaim.Status.REVOKED
            claim.save(update_fields=["attempts", "status", "updated_at"])
        security_logger.warning(
            "claim.failed", extra={"phone_tail": phone[-4:], "reason": "invalid", "attempt": failures}
        )
    raise ClaimLocked() if failures >= max_attempts else ClaimInvalid()


def complete_claim(
    *, phone: str, code: str, password: str, email: str | None = None, name: str | None = None
) -> AuthResult:
    """#13. Verify the code, convert the offline record to an online account and sign it in."""
    phone = _phone_or_error(phone)
    code = _normalize_code(code)
    email = normalize_email_address(email)

    if _failures(phone) >= settings.CLAIM_MAX_ATTEMPTS:
        security_logger.warning("claim.failed", extra={"phone_tail": phone[-4:], "reason": "locked"})
        raise ClaimLocked()

    user = _claimable_user(phone)
    verified_claim_id = _verify(user, phone, code, email)

    # Correct code: validate everything else before consuming it, so mistakes can be retried.
    final_email = user.email or email
    if not final_email:
        raise ValidationFailed(details={"email": ["Enter your email address to finish."]})
    final_name = (name or "").strip() or user.name
    if len(final_name) < 2:
        raise ValidationFailed(details={"name": ["Enter your name."]})
    try:
        validate_password(password, user=User(name=final_name, email=final_email, phone=phone))
    except DjangoValidationError as exc:
        raise ValidationFailed(details={"password": list(exc.messages)}) from None

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        claim = (
            AccountClaim.objects.select_for_update()
            .filter(pk=verified_claim_id, user=locked, status=AccountClaim.Status.PENDING)
            .first()
        )
        if claim is None or not locked.is_offline or not locked.is_active:
            raise ClaimInvalid()  # consumed or replaced by a concurrent request between the two checks
        if locked.email is None and User.objects.filter(email=final_email).exclude(pk=locked.pk).exists():
            raise Conflict("An account with this email already exists.", code="EMAIL_TAKEN")

        now = timezone.now()
        claim.status = AccountClaim.Status.USED
        claim.used_at = now
        claim.save(update_fields=["status", "used_at", "updated_at"])
        AccountClaim.objects.filter(
            user=locked, channel__in=_CLAIM_CHANNELS, status=AccountClaim.Status.PENDING
        ).update(status=AccountClaim.Status.REVOKED)

        locked.email = final_email
        locked.name = final_name
        locked.is_offline = False
        locked.claimed_at = now
        locked.set_password(password)
        try:
            with transaction.atomic():
                locked.save()
        except IntegrityError:
            raise Conflict("An account with this email already exists.", code="EMAIL_TAKEN") from None
        audit.record(
            actor=locked,
            action="account.claimed",
            entity_type="user",
            entity_id=locked.pk,
            reason=f"Offline account claimed with {claim.channel}",
            changes={"is_offline": [True, False]},
        )

    _clear_failures(phone)
    security_logger.info("claim.completed", extra={"claimed_user_id": str(locked.pk), "channel": claim.channel})
    return AuthResult(user=locked, tokens=issue_tokens(locked))
