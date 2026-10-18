import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """Adds `Membership.seat` and `membership_one_live_per_seat` (T11 completion, SPEC.md 3.10).

    No membership can exist before this migration (no code creates one until T15), so the
    non-null column needs no default or backfill.
    """

    dependencies = [
        ("memberships", "0001_initial"),
        ("seats", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="seat",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="seats.seat",
            ),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(
                condition=Q(("state", "active")), fields=("seat",), name="membership_one_live_per_seat"
            ),
        ),
    ]
