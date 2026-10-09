"""Account business rules (BACKEND_ARCHITECTURE.md #6-#11, SPEC.md 4.6, SECURITY.md section 3).

Views stay thin: they parse input, call one of these functions and wrap the
result. Every state change happens here.
"""

import logging
from dataclasses import dataclass

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.core import audit
from apps.core.exceptions import AppError, Conflict, ValidationFailed
from apps.core.models import Domain

from .models import User, normalize_email_address
from .phone import InvalidPhone, mask_email, normalize_phone
from .selectors import find_identity
from .tokens import TokenPair, issue_tokens

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("apps.security")


class InvalidCredentials(AppError):
    status = 401
    code = "INVALID_CREDENTIALS"
    message = "Email or password is incorrect."


@dataclass(frozen=True)
class AuthResult:
    user: User
    tokens: TokenPair


def _phone_or_error(raw: str, field: str = "phone") -> str:
    try:
        return normalize_phone(raw)
    except InvalidPhone as exc:
        raise ValidationFailed(details={field: [str(exc)]}) from None


def _domain_for(role: str, domain_code: str | None) -> Domain | None:
    if not domain_code:
        return None
    if role != User.Role.STUDENT:
        raise ValidationFailed(details={"domain_code": ["Only students choose an exam domain."]})
    domain = Domain.objects.filter(code=domain_code, is_active=True).first()
    if domain is None:
        raise ValidationFailed(details={"domain_code": ["Choose a valid exam domain."]})
    return domain


def _validate_password(password: str, *, name: str, email: str | None, phone: str | None) -> None:
    probe = User(name=name, email=email, phone=phone)
    try:
        validate_password(password, user=probe)
    except DjangoValidationError as exc:
        raise ValidationFailed(details={"password": list(exc.messages)}) from None


def _reject_existing_identity(*, role: str, email: str, phone: str) -> None:
    """Apply the online-signup rules of SPEC.md 4.6 before creating an account."""
    match = find_identity(email=email, phone=phone)
    if match.by_email is None and match.by_phone is None:
        return

    offline = next((u for u in (match.by_email, match.by_phone) if u is not None and u.is_offline), None)
    if match.conflicting and offline is not None:
        raise Conflict(
            "This phone number and email belong to different accounts. Please contact your library.",
            code="IDENTITY_CONFLICT",
        )
    if offline is not None and role == User.Role.STUDENT:
        # Never auto-link: the student must prove ownership first (OFF-04, SECURITY.md 3).
        channels = (["email_otp"] if offline.email else []) + ["owner_code"]
        details = {"channels": channels}
        if offline.email:
            details["masked_email"] = mask_email(offline.email)
        logger.info("auth.claim_required", extra={"offline_user_id": str(offline.pk)})
        raise Conflict(
            "A library already added you as a member. Verify it's you to link your account.",
            code="CLAIM_REQUIRED",
            details=details,
        )
    if match.by_email is not None:
        raise Conflict("An account with this email already exists.", code="EMAIL_TAKEN")
    raise Conflict("An account with this phone number already exists.", code="PHONE_TAKEN")


def register(
    *, role: str, name: str, email: str, phone: str, password: str, domain_code: str | None = None
) -> AuthResult:
    """Create an owner or student account and sign it in (AUTH-01, AUTH-02)."""
    email = normalize_email_address(email)
    phone = _phone_or_error(phone)
    name = name.strip()
    domain = _domain_for(role, domain_code)
    _validate_password(password, name=name, email=email, phone=phone)
    _reject_existing_identity(role=role, email=email, phone=phone)

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            name=name,
            password=password,
            role=role,
            phone=phone,
            domain=domain,
        )
    logger.info("auth.registered", extra={"registered_user_id": str(user.pk), "role": role})
    return AuthResult(user=user, tokens=issue_tokens(user))


def login(*, email: str, password: str, request=None) -> AuthResult:
    """Authenticate with email and password (AUTH-03).

    Every failure (unknown email, wrong password, unclaimed offline record,
    deactivated account) returns the same generic error.
    """
    normalized = normalize_email_address(email) or ""
    user = authenticate(request, username=normalized, password=password) if normalized else None
    if user is None or not user.is_active:
        security_logger.warning("auth.login_failed", extra={"email": normalized})
        raise InvalidCredentials()
    security_logger.info("auth.login_succeeded", extra={"login_user_id": str(user.pk)})
    return AuthResult(user=user, tokens=issue_tokens(user))


def update_profile(
    user: User,
    *,
    name: str | None = None,
    phone: str | None = None,
    domain_code: str | None = None,
    domain_provided: bool = False,
) -> User:
    """Edit name, phone and (students) exam domain; email is not editable (AUTH-05, AUTH-06)."""
    before = {"name": user.name, "phone": user.phone, "domain": user.domain.code if user.domain else None}
    if name is not None:
        if not name.strip():
            raise ValidationFailed(details={"name": ["Enter your name."]})
        user.name = name.strip()
    if phone is not None:
        new_phone = _phone_or_error(phone)
        if new_phone != user.phone and User.objects.filter(phone=new_phone).exclude(pk=user.pk).exists():
            raise Conflict("An account with this phone number already exists.", code="PHONE_TAKEN")
        user.phone = new_phone
    if domain_provided:
        user.domain = _domain_for(user.role, domain_code) if domain_code else None

    after = {"name": user.name, "phone": user.phone, "domain": user.domain.code if user.domain else None}
    changes = audit.changes_between(before, after)
    if not changes:
        return user
    with transaction.atomic():
        user.save(update_fields=["name", "phone", "domain", "updated_at"])
        audit.record(actor=user, action="profile.update", entity_type="user", entity_id=user.pk, changes=changes)
    return user
