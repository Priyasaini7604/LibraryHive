"""Forgot / reset password (AUTH-15, BACKEND_ARCHITECTURE.md #13a and #13b, SECURITY.md sections 3 and 20)."""

import re
import threading
import time
from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core import mail
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts import password_reset
from apps.accounts.models import AccountClaim, User
from apps.accounts.tests.base import COOKIE, PASSWORD, AuthTestCase
from apps.core.models import AuditLog
from apps.core.tests.factories import make_student

NEW_PASSWORD = "Brand-new-Pass-987"
EMAIL = "asha@example.com"
NEUTRAL = "If an account exists for that email, we've sent a reset code."


class ResetTestCase(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.student = make_student(email=EMAIL, password=PASSWORD, name="Asha Rao")

    def request_reset(self, email=EMAIL):
        return self.post("password-reset/request/", {"email": email})

    def confirm(self, code, password=NEW_PASSWORD, email=EMAIL):
        return self.post("password-reset/confirm/", {"email": email, "code": code, "new_password": password})

    def issue_code(self, email=EMAIL) -> str:
        """Request a reset and read the 6-digit code from the sent email."""
        mail.outbox.clear()
        self.assertEqual(self.request_reset(email).status_code, 200)
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def pending_claim(self, user=None):
        return AccountClaim.objects.get(
            user=user or self.student, channel="password_reset", status=AccountClaim.Status.PENDING
        )


class ResetRequestTests(ResetTestCase):
    def test_eligible_account_gets_an_email_with_a_hashed_single_code(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"], {"message": NEUTRAL})

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [EMAIL])
        self.assertIn("password reset code", message.subject.lower())
        code = re.search(r"\b(\d{6})\b", message.body).group(1)
        self.assertIn("30 minutes", message.body)

        claim = self.pending_claim()
        self.assertNotEqual(claim.code_hash, code)
        self.assertNotIn(code, claim.code_hash)
        self.assertTrue(check_password(code, claim.code_hash))
        self.assertLessEqual(len(claim.code_hash), 128)
        self.assertAlmostEqual((claim.expires_at - timezone.now()).total_seconds(), 30 * 60, delta=10)
        self.assertEqual(claim.attempts, 0)

    def test_response_is_identical_for_every_kind_of_email_and_no_email_is_sent(self):
        User.objects.create_user(
            email="off@example.com", name="Offline", role="student", is_offline=True, phone="+919811100020"
        )
        gone = make_student(email="gone@example.com", password=PASSWORD)
        gone.is_active = False
        gone.save()

        def shape(response):
            body = response.json()
            body.pop("request_id")
            return response.status_code, body

        known = shape(self.request_reset())
        mail.outbox.clear()
        for email in ("nobody@example.com", "off@example.com", "gone@example.com"):
            with self.subTest(email=email):
                self.assertEqual(shape(self.request_reset(email)), known)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(AccountClaim.objects.filter(user__email__in=["off@example.com", "gone@example.com"]))

    def test_email_is_case_and_space_insensitive(self):
        self.assertEqual(self.request_reset("  ASHA@Example.COM ").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_new_request_revokes_the_previous_code(self):
        first = self.issue_code()
        second = self.issue_code()
        self.assertEqual(AccountClaim.objects.filter(user=self.student, status="pending").count(), 1)
        self.assertEqual(AccountClaim.objects.filter(user=self.student, status="revoked").count(), 1)
        self.assertEqual(self.confirm(first).status_code, 400)
        self.assertEqual(self.confirm(second).status_code, 200)

    def test_invalid_email_format_is_a_validation_error(self):
        self.assertError(self.request_reset("not-an-email"), 400, "VALIDATION_ERROR")

    def test_email_send_failure_does_not_change_the_response(self):
        with mock.patch("apps.accounts.password_reset.send_mail", side_effect=OSError("smtp down")):
            with self.assertLogs("apps.accounts.password_reset", level="ERROR") as logs:
                response = self.request_reset()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"message": NEUTRAL})
        self.assertIn("email.failed", logs.output[0])

    def test_request_is_logged_as_a_security_event(self):
        with self.assertLogs("apps.security", level="INFO") as logs:
            self.request_reset()
            self.request_reset("nobody@example.com")
        found = [r.account_found for r in logs.records if r.getMessage() == "auth.password_reset_requested"]
        self.assertEqual(found, [True, False])

    def test_three_requests_per_ten_minutes_per_email_then_429_even_for_unknown_emails(self):
        for email in (EMAIL, "nobody@example.com"):
            with self.subTest(email=email):
                for _ in range(3):
                    self.assertEqual(self.request_reset(email).status_code, 200)
                response = self.request_reset(email)
                self.assertError(response, 429, "RATE_LIMITED")
                self.assertIn("Retry-After", response)

    def test_ten_requests_per_hour_per_ip(self):
        for n in range(10):
            self.assertEqual(self.request_reset(f"user{n}@example.com").status_code, 200)
        self.assertError(self.request_reset("another@example.com"), 429, "RATE_LIMITED")

    @override_settings(PASSWORD_RESET_MIN_RESPONSE_SECONDS=0.3)
    def test_every_request_takes_at_least_the_minimum_time(self):
        for email in (EMAIL, "nobody@example.com"):
            started = time.monotonic()
            self.request_reset(email)
            self.assertGreaterEqual(time.monotonic() - started, 0.29, email)


class ResetConfirmTests(ResetTestCase):
    def test_success_changes_password_audits_and_notifies_without_issuing_tokens(self):
        code = self.issue_code()
        mail.outbox.clear()

        response = self.confirm(code)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"], {"message": "Your password has been changed. Please log in."})
        self.assertNotIn("access", response.json()["data"])
        self.assertNotIn(COOKIE, response.cookies)

        self.assertEqual(self.login(password=PASSWORD).status_code, 401)
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, 200)

        claim = AccountClaim.objects.get(user=self.student)
        self.assertEqual(claim.status, "used")
        self.assertIsNotNone(claim.used_at)

        entry = AuditLog.objects.get(action="account.password_reset")
        self.assertEqual((entry.actor, entry.entity_id), (self.student, self.student.pk))
        self.assertNotIn(NEW_PASSWORD, str(entry.changes))
        self.assertNotIn(code, str(entry.changes))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password was changed", mail.outbox[0].subject.lower())
        self.assertNotIn(NEW_PASSWORD, mail.outbox[0].body)

    def test_all_refresh_tokens_are_blacklisted_so_every_device_is_signed_out(self):
        cookies = []
        for _ in range(2):  # two devices
            cookies.append(self.login().cookies[COOKIE].value)
        code = self.issue_code()
        self.assertEqual(self.confirm(code).status_code, 200)
        for cookie in cookies:
            self.client.cookies[COOKIE] = cookie
            self.assertError(self.post("refresh/"), 401, "TOKEN_INVALID")

    def test_a_code_works_only_once(self):
        code = self.issue_code()
        self.assertEqual(self.confirm(code).status_code, 200)
        self.assertError(self.confirm(code, password="Another-Pass-456"), 400, "RESET_INVALID")
        self.assertEqual(self.login(password=NEW_PASSWORD).status_code, 200)

    def test_wrong_code_is_rejected_and_counted(self):
        code = self.issue_code()
        wrong = "000000" if code != "000000" else "111111"
        self.assertError(self.confirm(wrong), 400, "RESET_INVALID")
        self.assertEqual(self.pending_claim().attempts, 1)
        self.assertEqual(self.login(password=PASSWORD).status_code, 200)  # password unchanged
        self.assertEqual(self.confirm(code).status_code, 200)  # the right code still works

    def test_five_wrong_attempts_lock_the_code_even_for_the_right_one(self):
        code = self.issue_code()
        wrong = "000000" if code != "000000" else "111111"
        statuses = [self.confirm(wrong).status_code for _ in range(5)]
        self.assertEqual(statuses, [400, 400, 400, 400, 429])
        self.assertError(self.confirm(code), 429, "CLAIM_LOCKED")
        self.assertEqual(AccountClaim.objects.get(user=self.student).status, "revoked")
        self.assertEqual(self.login(password=PASSWORD).status_code, 200)

        fresh = self.issue_code()  # a new request starts a new budget
        self.assertEqual(self.confirm(fresh).status_code, 200)

    def test_lockout_looks_the_same_for_unknown_emails(self):
        known = self.issue_code()
        wrong = "000000" if known != "000000" else "111111"
        known_statuses = [self.confirm(wrong).status_code for _ in range(5)]
        unknown_statuses = [self.confirm(wrong, email="nobody@example.com").status_code for _ in range(5)]
        self.assertEqual(known_statuses, unknown_statuses)
        self.assertEqual(unknown_statuses, [400, 400, 400, 400, 429])

    def test_expired_code_is_rejected_and_marked_expired(self):
        code = self.issue_code()
        AccountClaim.objects.filter(user=self.student).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertError(self.confirm(code), 400, "RESET_INVALID")
        self.assertEqual(AccountClaim.objects.get(user=self.student).status, "expired")
        self.assertEqual(self.login(password=PASSWORD).status_code, 200)

    def test_weak_password_does_not_consume_the_code(self):
        code = self.issue_code()
        response = self.confirm(code, password="password")
        self.assertError(response, 400, "VALIDATION_ERROR")
        self.assertIn("new_password", response.json()["details"])
        claim = self.pending_claim()
        self.assertEqual(claim.attempts, 0)
        self.assertEqual(self.confirm(code, password=NEW_PASSWORD).status_code, 200)

    def test_code_format_is_validated(self):
        for bad in ("abcdef", "12345", "1234567", ""):
            with self.subTest(code=bad):
                response = self.confirm(bad)
                self.assertError(response, 400, "VALIDATION_ERROR")
                self.assertIn("code", response.json()["details"])

    def test_one_users_code_cannot_reset_another_users_password(self):
        other = make_student(email="other@example.com", password=PASSWORD)
        code = self.issue_code()
        self.assertError(self.confirm(code, email=other.email), 400, "RESET_INVALID")
        other.refresh_from_db()
        self.assertTrue(other.check_password(PASSWORD))

    def test_deactivated_account_cannot_complete_a_reset(self):
        code = self.issue_code()
        self.student.is_active = False
        self.student.save()
        self.assertError(self.confirm(code), 400, "RESET_INVALID")

    def test_offline_record_cannot_reset(self):
        offline = User.objects.create_user(
            email="off@example.com", name="Offline", role="student", is_offline=True, phone="+919811100021"
        )
        self.assertError(self.confirm("123456", email=offline.email), 400, "RESET_INVALID")
        offline.refresh_from_db()
        self.assertFalse(offline.has_usable_password())

    def test_failed_attempts_are_logged_without_the_code(self):
        code = self.issue_code()
        wrong = "000000" if code != "000000" else "111111"
        with self.assertLogs("apps.security", level="WARNING") as logs:
            self.confirm(wrong)
        record = logs.records[0]
        self.assertEqual(record.getMessage(), "auth.password_reset_failed")
        self.assertNotIn(wrong, str(vars(record)))


class ResetConcurrencyTests(TransactionTestCase):
    """The same code used by two simultaneous requests succeeds exactly once."""

    def test_only_one_of_two_simultaneous_confirmations_succeeds(self):
        student = make_student(email=EMAIL, password=PASSWORD)
        password_reset.request_password_reset(email=EMAIL)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def worker(password: str):
            try:
                barrier.wait()
                password_reset.confirm_password_reset(email=EMAIL, code=code, new_password=password)
                outcomes.append("ok")
            except Exception as exc:  # collected and asserted below
                outcomes.append(type(exc).__name__)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(f"Concurrent-Pass-{n}-9",)) for n in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(outcomes), ["ResetInvalid", "ok"])
        student.refresh_from_db()
        self.assertEqual(AccountClaim.objects.filter(user=student, status="used").count(), 1)


class AccountClaimModelTests(TestCase):
    def test_only_one_pending_code_per_user_and_channel(self):
        from django.db import IntegrityError, transaction

        user = make_student()
        AccountClaim.objects.create(
            user=user, channel="password_reset", code_hash="x", expires_at=timezone.now() + timedelta(minutes=5)
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountClaim.objects.create(
                user=user, channel="password_reset", code_hash="y", expires_at=timezone.now() + timedelta(minutes=5)
            )
        AccountClaim.objects.filter(user=user).update(status="used")
        AccountClaim.objects.create(
            user=user, channel="password_reset", code_hash="z", expires_at=timezone.now() + timedelta(minutes=5)
        )

    def test_owner_codes_need_an_issuer_and_channels_are_restricted(self):
        from django.db import IntegrityError, transaction

        user = make_student()
        soon = timezone.now() + timedelta(minutes=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountClaim.objects.create(user=user, channel="owner_code", code_hash="x", expires_at=soon)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountClaim.objects.create(user=user, channel="sms", code_hash="x", expires_at=soon)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountClaim.objects.create(user=user, channel="email_otp", status="bogus", code_hash="x", expires_at=soon)
