"""The browser end-to-end environment can only ever target the dedicated database (config.settings.e2e)."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from config.e2e_guard import E2E_DATABASE_NAME, e2e_database_errors

BACKEND = Path(__file__).resolve().parents[3]
DEV_URL = "postgres://dev:dev-password@localhost:5432/libraryhive"
E2E_URL = f"postgres://dev:dev-password@localhost:5432/{E2E_DATABASE_NAME}"


class GuardFunctionTests(SimpleTestCase):
    def test_the_dedicated_local_database_is_accepted(self):
        self.assertEqual(e2e_database_errors(E2E_URL, other_urls=(DEV_URL,)), [])
        self.assertEqual(e2e_database_errors(E2E_URL.replace("localhost", "127.0.0.1")), [])

    def test_an_unset_url_is_refused(self):
        self.assertTrue(e2e_database_errors(""))

    def test_any_other_database_name_is_refused(self):
        for name in ("libraryhive", "libraryhive_db", "libraryhive_e2e_old", "postgres", "libraryhive_prod"):
            with self.subTest(name=name):
                self.assertTrue(e2e_database_errors(f"postgres://u:p@localhost/{name}"))

    def test_a_remote_host_is_refused_even_with_the_right_name(self):
        for host in ("db.example.com", "10.0.0.5", "libraryhive.render.com"):
            with self.subTest(host=host):
                self.assertTrue(e2e_database_errors(f"postgres://u:p@{host}:5432/{E2E_DATABASE_NAME}"))

    def test_a_non_postgres_url_is_refused(self):
        self.assertTrue(e2e_database_errors(f"sqlite:///{E2E_DATABASE_NAME}"))
        self.assertTrue(e2e_database_errors(f"mysql://u:p@localhost/{E2E_DATABASE_NAME}"))

    def test_it_must_differ_from_the_normal_database_url(self):
        self.assertTrue(e2e_database_errors(E2E_URL, other_urls=(E2E_URL,)))

    def test_error_messages_never_contain_the_password(self):
        errors = e2e_database_errors("postgres://u:s3cret-pw@db.example.com/libraryhive")
        self.assertNotIn("s3cret-pw", " ".join(errors))


class E2ESettingsModuleTests(SimpleTestCase):
    """Import `config.settings.e2e` in a fresh interpreter, exactly as the browser suite's server does."""

    def load(self, env: dict, code: str) -> subprocess.CompletedProcess:
        full_env = {k: v for k, v in os.environ.items() if k not in {"E2E_DATABASE_URL", "DJANGO_SETTINGS_MODULE"}}
        full_env.update({"DATABASE_URL": DEV_URL, "DJANGO_SETTINGS_MODULE": "config.settings.e2e", **env})
        return subprocess.run(
            [sys.executable, "-c", code], cwd=BACKEND, env=full_env, capture_output=True, text=True, timeout=120
        )

    def test_refuses_to_load_without_the_dedicated_database(self):
        result = self.load({}, "from django.conf import settings; settings.DATABASES")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to start the e2e environment", result.stderr)

    def test_refuses_to_load_pointed_at_the_normal_database(self):
        result = self.load({"E2E_DATABASE_URL": DEV_URL}, "from django.conf import settings; settings.DATABASES")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to start the e2e environment", result.stderr)

    def test_only_the_e2e_database_and_dummy_payment_keys_are_used(self):
        code = (
            "from django.conf import settings as s;"
            "print(s.DATABASES['default']['NAME']);"
            "print(s.RAZORPAY_KEY_ID);"
            "print(s.RAZORPAY_KEY_SECRET);"
            "print(s.ENVIRONMENT)"
        )
        real_looking = {"RAZORPAY_KEY_ID": "rzp_test_REALKEY", "RAZORPAY_KEY_SECRET": "REALSECRET"}
        result = self.load({"E2E_DATABASE_URL": E2E_URL, **real_looking}, code)
        self.assertEqual(result.returncode, 0, result.stderr)
        name, key_id, key_secret, environment = result.stdout.split()
        self.assertEqual(name, E2E_DATABASE_NAME)
        self.assertEqual((key_id, key_secret, environment), ("rzp_test_e2e_dummy", "e2e-dummy-key-secret", "e2e"))
