from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel


class Membership(BaseModel):
    """One student's tenure at one library (SPEC.md 3.10).

    Only the lifecycle `state` is stored. The status students and owners see
    (active, due, overdue, archived) is derived from `next_due_date` by
    `memberships.selectors.annotate_status` (decision D5), so it never depends
    on a job having run. Memberships are never deleted.

    The `seat` foreign key (one occupant per seat, `membership_one_live_per_seat`)
    is added in a follow-up migration as soon as the `seats.Seat` model exists
    (T10); see IMPLEMENTATION_PLAN.md T11.
    """

    class Source(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Owner-assisted"

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships")
    library = models.ForeignKey("libraries.Library", on_delete=models.PROTECT, related_name="memberships")
    plan = models.ForeignKey("libraries.PricingPlan", on_delete=models.PROTECT, related_name="memberships")
    source = models.CharField(max_length=10, choices=Source.choices)
    state = models.CharField(max_length=10, choices=State.choices, default=State.ACTIVE)
    start_date = models.DateField()
    next_due_date = models.DateField()
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    archive_reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        indexes = [
            models.Index(fields=["library", "state", "next_due_date"], name="membership_library_due_idx"),
            models.Index(fields=["student", "state"], name="membership_student_state_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "library"],
                condition=Q(state="active"),
                name="membership_one_live_per_student_library",
            ),
            models.CheckConstraint(
                condition=~Q(state="archived") | Q(archived_at__isnull=False),
                name="membership_archive_fields",
            ),
            models.CheckConstraint(condition=Q(next_due_date__gt=F("start_date")), name="membership_due_after_start"),
            models.CheckConstraint(condition=Q(source__in=["online", "offline"]), name="membership_source_valid"),
            models.CheckConstraint(condition=Q(state__in=["active", "archived"]), name="membership_state_valid"),
        ]

    def __str__(self):
        return f"membership {self.pk} ({self.state})"
