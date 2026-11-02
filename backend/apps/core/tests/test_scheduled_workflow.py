"""The scheduled-jobs GitHub Actions workflow keeps its safety properties (BACKEND_ARCHITECTURE.md 11.4).

These tests read `.github/workflows/scheduled-jobs.yml` and fail if an edit would let a branch other than `main`, a
fork, or a manual input reach the database secrets, or would schedule payment reconciliation or email delivery.
They check the file only; they never run the workflow and never read a secret.
"""

import re
from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

WORKFLOW = Path(settings.BASE_DIR).parent / ".github" / "workflows" / "scheduled-jobs.yml"
SECRET_NAMES = {"DATABASE_URL", "SECRET_KEY", "JWT_SIGNING_KEY"}
ALLOWED_STEPS = {"renewal_notifications", "owner_summaries", "auto_close_attendance"}
MAIN_ONLY = "github.ref == 'refs/heads/main'"
REPOSITORY = "github.repository == 'Priyasaini7604/LibraryHive'"


def load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return workflow.get("on", workflow.get(True))


def environment_name(job: dict):
    environment = job.get("environment")
    return environment.get("name") if isinstance(environment, dict) else environment


class WorkflowSecurityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workflow = load()
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.jobs = cls.workflow["jobs"]

    def test_it_can_only_be_started_by_the_schedule_or_by_hand(self):
        self.assertEqual(set(triggers(self.workflow)), {"schedule", "workflow_dispatch"})
        crons = [entry["cron"] for entry in triggers(self.workflow)["schedule"]]
        self.assertEqual(crons, ["37 3 * * *", "17 * * * *"])  # 09:07 IST daily, hh:47 IST hourly

    def test_no_pull_request_trigger_so_forks_and_pr_branches_never_run_it(self):
        self.assertNotRegex(self.text, r"pull_request")
        self.assertNotIn("secrets: inherit", self.text)

    def test_secrets_are_only_read_by_jobs_that_use_the_staging_environment(self):
        for name, job in self.jobs.items():
            uses_secrets = "secrets." in yaml.safe_dump(job)
            if uses_secrets:
                self.assertEqual(environment_name(job), "staging", f"job {name} reads secrets outside `staging`")
        self.assertEqual(environment_name(self.jobs["run"]), "staging")

    def test_the_job_without_the_environment_has_no_secret_at_all(self):
        wrong_branch = self.jobs["wrong-branch"]
        self.assertIsNone(wrong_branch.get("environment"))
        self.assertNotIn("secrets.", yaml.safe_dump(wrong_branch))

    def test_exactly_the_three_secrets_are_used_and_only_in_step_environments(self):
        referenced = set(re.findall(r"secrets\.([A-Z_]+)", self.text))
        self.assertEqual(referenced, SECRET_NAMES)
        run = self.jobs["run"]
        self.assertNotIn("secrets.", yaml.safe_dump(run.get("env", {})), "secrets must not be job-wide")
        for step in run["steps"]:
            if "secrets." in yaml.safe_dump(step):
                self.assertTrue(set(step.get("env", {})) <= SECRET_NAMES | {"ARGS"}, step.get("name"))
                self.assertNotIn("with", step, "a secret must not be passed to an action")
        install = next(step for step in run["steps"] if step.get("name") == "Install dependencies")
        self.assertNotIn("secrets.", yaml.safe_dump(install), "third-party install code must not see secrets")

    def test_the_run_job_needs_the_main_branch_and_the_real_repository(self):
        condition = self.jobs["run"]["if"]
        self.assertIn(MAIN_ONLY, condition)
        self.assertIn(REPOSITORY, condition)
        self.assertIn("!=", self.jobs["wrong-branch"]["if"])  # the other branches get a loud failure instead

    def test_permissions_are_read_only(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        for job in self.jobs.values():
            self.assertNotIn("permissions", job, "a job must not widen the workflow permissions")

    def test_manual_runs_default_to_a_dry_run_and_only_offer_the_two_jobs(self):
        inputs = triggers(self.workflow)["workflow_dispatch"]["inputs"]
        self.assertIs(inputs["dry_run"]["default"], True)
        self.assertEqual(inputs["job"]["options"], ["daily", "attendance"])

    def test_only_the_notification_and_attendance_steps_can_ever_run(self):
        steps = set(re.findall(r"--only (\w+)", self.text))
        self.assertEqual(steps, ALLOWED_STEPS)
        for forbidden in ("reconcile_payments", "send_emails", "expire_holds"):
            self.assertNotRegex(self.text, rf"--only {forbidden}")
        self.assertEqual(self.jobs["run"]["env"]["EMAIL_NOTIFICATIONS_ENABLED"], "false")

    def test_the_schema_is_only_checked_never_migrated(self):
        self.assertIn("python manage.py migrate --check", self.text)
        self.assertNotRegex(self.text, r"manage\.py migrate(?! --check)")
        self.assertNotRegex(self.text, r"manage\.py (flush|loaddata|createcachetable|dbshell|sqlmigrate)")

    def test_daily_and_hourly_runs_never_share_a_concurrency_group(self):
        concurrency = self.workflow["concurrency"]
        self.assertIs(concurrency["cancel-in-progress"], False)
        group = concurrency["group"]
        self.assertIn("'attendance'", group)
        self.assertIn("'daily'", group)
        self.assertIn("-offbranch", group)
        self.assertIn("-dry", group)

    def test_validation_steps_before_checkout_run_from_the_workspace_root(self):
        """Regression: before `actions/checkout` the `backend/` folder does not exist, so a `run` step that inherits
        the job's `working-directory: backend` cannot even start (run 41486751959)."""
        run = self.jobs["run"]
        self.assertEqual(run["defaults"]["run"]["working-directory"], "backend")  # steps after checkout keep it
        steps = run["steps"]
        checkout = next(i for i, step in enumerate(steps) if str(step.get("uses", "")).startswith("actions/checkout"))
        before = steps[:checkout]
        names = [step.get("name") for step in before]
        # The fail-fast validation stays ahead of checkout, in this order.
        self.assertEqual(
            names, ["Choose the job", "Check the secrets are set", "Check the database connection settings"]
        )
        for step in before:
            if "run" in step:
                self.assertEqual(
                    step.get("working-directory"),
                    ".",
                    f"step {step['name']!r} runs before checkout and must set `working-directory: .`",
                )
        # Steps after checkout must not be moved out of backend/ by accident.
        for step in steps[checkout + 1 :]:
            self.assertNotIn("working-directory", step, f"step {step.get('name')!r} should inherit backend")

    def test_the_run_has_a_timeout_and_the_database_url_is_checked_without_printing_it(self):
        self.assertLessEqual(self.jobs["run"]["timeout-minutes"], 10)
        self.assertIn("sslmode=require", self.text)
        self.assertIn("-pooler", self.text)
        self.assertNotRegex(self.text, r"echo[^\n]*\$\{?DATABASE_URL")
