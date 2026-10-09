"""Seed the controlled vocabularies (SPEC.md 3.3) and create the cache table.

The database cache backs DRF throttling (no Redis). Creating it in a migration
means a fresh database needs no manual `createcachetable` step.
"""

from django.core.management import call_command
from django.db import migrations

DOMAINS = [
    ("upsc", "UPSC"),
    ("ssc", "SSC"),
    ("neet", "NEET"),
    ("jee", "JEE"),
    ("gate", "GATE"),
    ("ca", "CA"),
    ("banking", "Banking"),
    ("cat", "CAT"),
    ("state_psc", "State PSC"),
    ("general", "General Study"),
]

AMENITIES = [
    ("wifi", "WiFi"),
    ("ac", "Air conditioning"),
    ("power_socket", "Power socket at desk"),
    ("ro_water", "RO drinking water"),
    ("ergonomic_chair", "Ergonomic chairs"),
    ("locker", "Lockers"),
    ("cctv", "CCTV"),
    ("discussion_room", "Discussion room"),
    ("power_backup", "Power backup"),
    ("parking", "Parking"),
    ("washroom", "Washroom"),
]


def seed(apps, schema_editor):
    for model_name, rows in (("Domain", DOMAINS), ("Amenity", AMENITIES)):
        model = apps.get_model("core", model_name)
        for order, (code, name) in enumerate(rows):
            model.objects.update_or_create(code=code, defaults={"name": name, "sort_order": order})


def unseed(apps, schema_editor):
    for model_name, rows in (("Domain", DOMAINS), ("Amenity", AMENITIES)):
        apps.get_model("core", model_name).objects.filter(code__in=[code for code, _ in rows]).delete()


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


def drop_cache_table(apps, schema_editor):
    schema_editor.execute("DROP TABLE IF EXISTS core_cache")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
