import uuid

from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    """UUID primary key and timestamps for every domain entity (AGENTS.md 2.2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Vocabulary(BaseModel):
    """Controlled list entry, managed through Django admin (SPEC.md 3.3)."""

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=60)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Domain(Vocabulary):
    """Exam / stream a student prepares for, e.g. UPSC, NEET."""

    class Meta(Vocabulary.Meta):
        pass


class Amenity(Vocabulary):
    """Library facility, e.g. WiFi, air conditioning."""

    class Meta(Vocabulary.Meta):
        verbose_name_plural = "amenities"


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError("Audit log entries are append-only and cannot be updated.")

    def delete(self):
        raise TypeError("Audit log entries are append-only and cannot be deleted.")


class AuditLog(BaseModel):
    """Append-only business audit trail (SPEC.md 3.4, FEATURES LOG-06).

    Write through `apps.core.audit.record()` inside the same transaction as the
    change being audited. The `library` scope column is added together with
    the Library model (task T08).
    """

    class ActorRole(models.TextChoices):
        OWNER = "owner", "Owner"
        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"
        SYSTEM = "system", "System"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    actor_role = models.CharField(max_length=10, choices=ActorRole.choices)
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=40)
    entity_id = models.UUIDField()
    changes = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="auditlog_entity_idx"),
            models.Index(fields=["actor", "-created_at"], name="auditlog_actor_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(actor_role__in=["owner", "student", "staff", "system"]),
                name="auditlog_actor_role_valid",
            ),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}:{self.entity_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Audit log entries are append-only and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Audit log entries are append-only and cannot be deleted.")
