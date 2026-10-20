"""Prepare the dedicated e2e database (run with DJANGO_SETTINGS_MODULE=config.settings.e2e).

Applies migrations and loads the demo data. It never creates, drops or truncates a database: if
`libraryhive_e2e` does not exist it stops and prints the exact command for a person to run.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection

from config.e2e_guard import E2E_DATABASE_NAME, e2e_database_errors


class Command(BaseCommand):
    help = "Migrate and seed the dedicated e2e database (refuses any other database)."

    def handle(self, *args, **options):
        db = connection.settings_dict
        host = db["HOST"] or "localhost"
        errors = e2e_database_errors(f"postgres://{host}:{db['PORT'] or 5432}/{db['NAME']}")
        if errors:
            raise CommandError("Not touching this database: " + " ".join(errors))
        try:
            connection.ensure_connection()
        except OperationalError as exc:
            raise CommandError(
                f"Cannot connect to '{E2E_DATABASE_NAME}'. If it does not exist yet, a person must create it once:\n"
                f'  docker compose exec db psql -U <postgres user> -c "CREATE DATABASE {E2E_DATABASE_NAME};"\n'
                f"({type(exc).__name__})"
            ) from exc
        self.stdout.write(f"Target verified: database '{E2E_DATABASE_NAME}' on {host}.")
        call_command("migrate", interactive=False, verbosity=0)
        call_command("seed_demo", force=True, verbosity=0)
        self.stdout.write(self.style.SUCCESS("e2e database is migrated and seeded."))
