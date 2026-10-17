from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import BaseModel

e164_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Phone numbers are stored in E.164 format, e.g. +919876543210.",
)


def normalize_email_address(email: str | None) -> str | None:
    """Emails are stored trimmed and lowercased (SPEC.md section 1)."""
    if email is None:
        return None
    email = email.strip().lower()
    return email or None


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, name, password=None, role="student", **extra_fields):
        email = normalize_email_address(email)
        if not email and not extra_fields.get("is_offline"):
            raise ValueError("An email address is required.")
        user = self.model(email=email, name=name, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        # Platform staff use Django admin, not the owner/student product flows.
        extra_fields.setdefault("role", User.Role.OWNER)
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self.create_user(email, name, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """Every person in the system: owners, online students and offline students.

    SPEC.md 3.1. Offline students are created by owners with no password and
    no login until they claim their account (SPEC.md 4.6).
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Library owner"
        STUDENT = "student", "Student"

    name = models.CharField(max_length=150)
    # NULL (not "") when absent, so several rows without a value never collide on the unique constraints.
    email = models.EmailField(max_length=254, null=True, blank=True)  # noqa: DJ001
    phone = models.CharField(max_length=16, null=True, blank=True, validators=[e164_validator])  # noqa: DJ001
    role = models.CharField(max_length=10, choices=Role.choices)
    domain = models.ForeignKey(
        "core.Domain",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_offline = models.BooleanField(default=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        indexes = [models.Index(fields=["role"], name="user_role_idx")]
        constraints = [
            models.UniqueConstraint(fields=["email"], name="user_email_unique"),
            models.UniqueConstraint(fields=["phone"], name="user_phone_unique"),
            models.CheckConstraint(condition=Q(role__in=["owner", "student"]), name="user_role_valid"),
            models.CheckConstraint(
                condition=Q(email__isnull=True) | Q(email=Lower("email")),
                name="user_email_lowercase",
            ),
            models.CheckConstraint(condition=Q(is_offline=False) | Q(role="student"), name="user_offline_is_student"),
            models.CheckConstraint(
                condition=Q(is_offline=True) | Q(email__isnull=False) | Q(is_staff=True),
                name="user_online_has_email",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.role})"

    def save(self, *args, **kwargs):
        self.email = normalize_email_address(self.email)
        self.name = (self.name or "").strip()
        super().save(*args, **kwargs)


class AccountClaim(BaseModel):
    """Short-lived one-time code that proves ownership (SPEC.md 3.2).

    Channels: `password_reset` (T05, AUTH-15) and, in T06, `email_otp` and
    `owner_code` for claiming an offline account (OFF-04). The plain code is
    never stored; only a hash made with Django's password hasher.

    The `library` column (owner codes are issued by an owner for their
    library) is added together with the Library model in T08.
    """

    class Channel(models.TextChoices):
        EMAIL_OTP = "email_otp", "Email code"
        OWNER_CODE = "owner_code", "Owner code"
        PASSWORD_RESET = "password_reset", "Password reset"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        USED = "used", "Used"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="claims")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    code_hash = models.CharField(max_length=128)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status"], name="accountclaim_user_status_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "channel"],
                condition=Q(status="pending"),
                name="accountclaim_one_pending",
            ),
            models.CheckConstraint(
                condition=Q(channel__in=["email_otp", "owner_code", "password_reset"]),
                name="accountclaim_channel_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "used", "expired", "revoked"]),
                name="accountclaim_status_valid",
            ),
            models.CheckConstraint(
                condition=~Q(channel="owner_code") | Q(issued_by__isnull=False),
                name="accountclaim_owner_code_has_issuer",
            ),
        ]

    def __str__(self):
        return f"{self.channel} for {self.user_id} ({self.status})"
