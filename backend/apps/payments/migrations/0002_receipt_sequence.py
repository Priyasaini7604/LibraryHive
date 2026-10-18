from django.db import migrations


class Migration(migrations.Migration):
    """The PostgreSQL sequence behind `Payment.receipt_number` (`LH-{YYYY}-{seq:06d}`, SPEC.md 3.11)."""

    dependencies = [("payments", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql="CREATE SEQUENCE IF NOT EXISTS payment_receipt_seq START 1",
            reverse_sql="DROP SEQUENCE IF EXISTS payment_receipt_seq",
        )
    ]
