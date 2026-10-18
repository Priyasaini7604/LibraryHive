"""Offline account claim (OFF-04, BACKEND_ARCHITECTURE.md #12 and #13, SECURITY.md sections 3 and 20)."""

import re
import threading
import time
from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core import mail
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts import claims
from apps.accounts.models import AccountClaim, User
from apps.accounts.tests.base import COOKIE, PASSWORD, AuthTestCase
from apps.core.models import AuditLog
from apps.core.tests.factories import make_owner, make_student

PHONE = "+919811100050"
PHONE_INPUT = "98111 00050"
EMAIL = "rahul@example.com"
NEW_PASSWORD = "Brand-new-Pass-987"


def make_offline(*, email=EMAIL, phone=PHONE, name="Rahul Sharma") -> User:
    return User.objects.create_user(email=email, name=name, role="student", is_offline=True, phone=phone)


class ClaimTestCase(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.offline = make_offline()
        self.owner = make_owner()

    def start(self, channel="email_otp", phone=PHONE_INPUT, **extra):
        return self.post("claim/start/", {"phone": phone, "channel": channel, **extra})

    def complete(self, code, password=NEW_PASSWORD, phone=PHONE_INPUT, **extra):
        return self.post("claim/complete/", {"phone": phone, "code": code, "password": password, **extra})

    def otp(self, **extra) -> str:
        mail.outbox.clear()
        self.assertEqual(self.start(**extra).status_code, 200)
        return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def owner_code(self, student=None) -> str:
        code, _ = claims.issue_claim_code(student=student or self.offline, issued_by=self.owner)
        return code

    def pending(self, channel, user=None):
        return AccountClaim.objects.get(user=user or self.offline, channel=channel, status="pending")


class ClaimStartTests(ClaimTestCase):
    def test_email_otp_is_emailed_hashed_and_expires_in_ten_minutes(self):
        response = self.start()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"], {"channel": "email_otp", "masked_email": None})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EMAIL])
        code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
        self.assertIn("10 minutes", mail.outbox[0].body)

        claim = self.pending("email_otp")
        self.assertNotIn(code, claim.code_hash)
        self.assertTrue(check_password(code, claim.code_hash))
        self.assertAlmostEqual((claim.expires_at - timezone.now()).total_seconds(), 600, delta=10)

    def test_masked_email_echoes_the_callers_input_not_the_record(self):
        response = self.start(email="Rahul@Example.com")
        self.assertEqual(response.json()["data"]["masked_email"], "r***@example.com")
        response = self.start(phone="9811100099", email="other@example.com")
        self.assertEqual(response.json()["data"]["masked_email"], "o***@example.com")

    def test_response_is_identical_for_matching_and_unknown_phones_and_nothing_is_sent_for_unknown(self):
        def shape(response):
            body = response.json()
            body.pop("request_id")
            return response.status_code, body

        known = shape(self.start())
        mail.outbox.clear()
        self.assertEqual(shape(self.start(phone="9811100099")), known)
        self.assertEqual(shape(self.start("owner_code", phone="9811100099")), shape(self.start("owner_code")))
        self.assertEqual(mail.outbox, [])

    def test_wrong_email_for_the_record_sends_nothing(self):
        self.assertEqual(self.start(email="someone-else@example.com").status_code, 200)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(AccountClaim.objects.exists())

    def test_owner_code_channel_sends_nothing_and_creates_no_code(self):
        self.assertEqual(self.start("owner_code").status_code, 200)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(AccountClaim.objects.exists())

    def test_record_without_an_email_must_use_the_owner_code(self):
        make_offline(email=None, phone="+919811100051", name="No Email")
        self.assertError(self.start(phone="9811100051"), 400, "CLAIM_INVALID")
        self.assertEqual(mail.outbox, [])

    def test_online_accounts_and_deactivated_records_are_not_claimable(self):
        make_student(email="online@example.com", phone="+919811100052")
        gone = make_offline(email="gone@example.com", phone="+919811100053", name="Gone")
        gone.is_active = False
        gone.save()
        self.assertEqual(self.start(phone="9811100052").status_code, 200)
        self.assertEqual(self.start(phone="9811100053").status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_a_new_otp_revokes_the_previous_one(self):
        first = self.otp()
        second = self.otp()
        self.assertEqual(AccountClaim.objects.filter(user=self.offline, status="pending").count(), 1)
        self.assertEqual(AccountClaim.objects.filter(user=self.offline, status="revoked").count(), 1)
        self.assertError(self.complete(first), 400, "CLAIM_INVALID")
        self.assertEqual(self.complete(second).status_code, 200)

    def test_email_send_failure_is_a_502(self):
        with mock.patch("apps.accounts.password_reset.send_mail", side_effect=OSError("smtp down")):
            with self.assertLogs("apps.accounts.password_reset", level="ERROR"):
                response = self.start()
        self.assertError(response, 502, "EMAIL_FAILED")

    def test_invalid_input_is_a_validation_error(self):
        self.assertError(self.start(phone="123"), 400, "VALIDATION_ERROR")
        self.assertError(self.start(channel="sms"), 400, "VALIDATION_ERROR")
        self.assertError(self.start(email="not-an-email"), 400, "VALIDATION_ERROR")

    def test_three_starts_per_ten_minutes_per_phone_then_429_even_for_unknown_phones(self):
        for phone in (PHONE_INPUT, "9811100099"):
            with self.subTest(phone=phone):
                for _ in range(3):
                    self.assertEqual(self.start(phone=phone).status_code, 200)
                self.assertError(self.start(phone=phone), 429, "RATE_LIMITED")

    def test_ten_starts_per_hour_per_ip(self):
        for n in range(10):
            self.assertEqual(self.start(phone=f"98111 0{n:04d}").status_code, 200)
        self.assertError(self.start(phone="9811100999"), 429, "RATE_LIMITED")

    @override_settings(PASSWORD_RESET_MIN_RESPONSE_SECONDS=0.3)
    def test_every_start_takes_at_least_the_minimum_time(self):
        for phone in (PHONE_INPUT, "9811100099"):
            started = time.monotonic()
            self.start(phone=phone)
            self.assertGreaterEqual(time.monotonic() - started, 0.29, phone)

    def test_start_is_logged_without_the_full_phone(self):
        with self.assertLogs("apps.security", level="INFO") as logs:
            self.start()
        record = next(r for r in logs.records if r.getMessage() == "claim.started")
        self.assertTrue(record.match)
        self.assertNotIn(PHONE, str(vars(record)))


class ClaimCompleteTests(ClaimTestCase):
    def test_email_otp_claim_converts_the_same_user_and_signs_in(self):
        original_id = self.offline.pk
        response = self.complete(self.otp())
        self.assertEqual(response.status_code, 200, response.content)

        data = response.json()["data"]
        self.assertEqual(data["user"]["id"], str(original_id))
        self.assertEqual(data["user"]["email"], EMAIL)
        self.assertTrue(data["access"])
        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertNotIn(cookie.value, str(data))

        user = User.objects.get(pk=original_id)
        self.assertFalse(user.is_offline)
        self.assertIsNotNone(user.claimed_at)
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertEqual(User.objects.filter(phone=PHONE).count(), 1)
        self.assertEqual(self.pending_count(), 0)
        self.assertEqual(AccountClaim.objects.get(user=user).status, "used")

        # Normal login now works with the new password.
        self.assertEqual(self.login(EMAIL, NEW_PASSWORD).status_code, 200)

    def pending_count(self):
        return AccountClaim.objects.filter(user=self.offline, status="pending").count()

    def test_owner_code_claim_for_a_record_without_email_needs_the_email(self):
        bare = make_offline(email=None, phone="+919811100051", name="No Email")
        code = self.owner_code(bare)
        self.assertError(self.complete(code, phone="9811100051"), 400, "VALIDATION_ERROR")
        self.assertEqual(AccountClaim.objects.get(user=bare).status, "pending")  # not consumed

        response = self.complete(code.lower(), phone="9811100051", email="New.Email@Example.com")
        self.assertEqual(response.status_code, 200, response.content)
        bare.refresh_from_db()
        self.assertEqual(bare.email, "new.email@example.com")
        self.assertFalse(bare.is_offline)

    def test_owner_code_claim_with_an_email_on_file_needs_no_email_and_accepts_spaces_and_hyphens(self):
        code = self.owner_code()
        spaced = f"{code[:4]}-{code[4:]}".lower()
        self.assertEqual(self.complete(spaced).status_code, 200)

    def test_owner_code_for_a_record_without_email_cannot_take_an_email_that_is_already_registered(self):
        bare = make_offline(email=None, phone="+919811100051", name="No Email")
        make_student(email="taken@example.com", phone="+919811100060")
        code = self.owner_code(bare)
        self.assertError(self.complete(code, phone="9811100051", email="taken@example.com"), 409, "EMAIL_TAKEN")
        bare.refresh_from_db()
        self.assertTrue(bare.is_offline)
        self.assertEqual(AccountClaim.objects.get(user=bare).status, "pending")

    def test_optional_name_is_applied(self):
        self.assertEqual(self.complete(self.otp(), name="Rahul K. Sharma").status_code, 200)
        self.offline.refresh_from_db()
        self.assertEqual(self.offline.name, "Rahul K. Sharma")

    def test_a_weak_password_does_not_consume_the_code(self):
        code = self.otp()
        response = self.complete(code, password="12345678")
        self.assertError(response, 400, "VALIDATION_ERROR")
        self.assertIn("password", response.json()["details"])
        self.assertEqual(self.pending_count(), 1)
        self.assertEqual(self.complete(code).status_code, 200)

    def test_a_password_similar_to_the_email_is_rejected(self):
        code = self.otp()
        self.assertError(self.complete(code, password="rahul1234"), 400, "VALIDATION_ERROR")

    def test_wrong_code_is_rejected_and_counted(self):
        code = self.otp()
        wrong = "000000" if code != "000000" else "111111"
        self.assertError(self.complete(wrong), 400, "CLAIM_INVALID")
        self.assertEqual(self.pending("email_otp").attempts, 1)
        self.offline.refresh_from_db()
        self.assertTrue(self.offline.is_offline)

    def test_expired_code_is_rejected_and_marked_expired(self):
        code = self.otp()
        AccountClaim.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertError(self.complete(code), 400, "CLAIM_INVALID")
        self.assertEqual(AccountClaim.objects.get().status, "expired")

    def test_a_used_code_cannot_be_reused(self):
        code = self.otp()
        self.assertEqual(self.complete(code).status_code, 200)
        self.assertError(self.complete(code, password="Another-Pass-5551"), 400, "CLAIM_INVALID")

    def test_five_wrong_attempts_lock_the_claim_even_for_the_right_code(self):
        code = self.otp()
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(4):
            self.assertError(self.complete(wrong), 400, "CLAIM_INVALID")
        self.assertError(self.complete(wrong), 429, "CLAIM_LOCKED")
        self.assertEqual(AccountClaim.objects.get().status, "revoked")
        self.assertError(self.complete(code), 429, "CLAIM_LOCKED")
        self.offline.refresh_from_db()
        self.assertTrue(self.offline.is_offline)

    def test_lockout_also_applies_to_phones_without_a_record(self):
        for _ in range(4):
            self.assertError(self.complete("123456", phone="9811100099"), 400, "CLAIM_INVALID")
        self.assertError(self.complete("123456", phone="9811100099"), 429, "CLAIM_LOCKED")

    def test_a_fresh_code_after_a_lockout_works(self):
        wrong = "000000"
        self.otp()
        for _ in range(5):
            self.complete(wrong)
        code = self.otp()  # requesting a new code starts a new attempt budget
        self.assertEqual(self.complete(code).status_code, 200)

    def test_owner_code_and_otp_are_independent_and_both_revoked_after_a_claim(self):
        otp = self.otp()
        owner = self.owner_code()
        self.assertEqual(AccountClaim.objects.filter(user=self.offline, status="pending").count(), 2)
        self.assertEqual(self.complete(owner).status_code, 200)
        self.assertEqual(AccountClaim.objects.filter(user=self.offline, status="pending").count(), 0)
        self.assertEqual(AccountClaim.objects.get(channel="email_otp").status, "revoked")
        self.assertError(self.complete(otp, password="Another-Pass-5551"), 400, "CLAIM_INVALID")

    def test_a_wrong_email_for_the_record_fails_even_with_the_right_code(self):
        code = self.otp()
        self.assertError(self.complete(code, email="someone-else@example.com"), 400, "CLAIM_INVALID")
        self.offline.refresh_from_db()
        self.assertTrue(self.offline.is_offline)

    def test_the_code_is_bound_to_the_phone_it_was_issued_for(self):
        other = make_offline(email="other@example.com", phone="+919811100061", name="Other Student")
        code = self.otp()
        self.assertError(self.complete(code, phone="9811100061"), 400, "CLAIM_INVALID")
        other.refresh_from_db()
        self.assertTrue(other.is_offline)

    def test_names_are_never_used_for_matching(self):
        code = self.otp()
        self.assertError(self.complete(code, phone="9811100077", name="Rahul Sharma"), 400, "CLAIM_INVALID")

    def test_online_account_cannot_be_taken_over_by_a_code_for_its_phone(self):
        online = make_student(email="online@example.com", phone="+919811100052")
        self.assertError(self.complete("123456", phone="9811100052"), 400, "CLAIM_INVALID")
        online.refresh_from_db()
        self.assertTrue(online.check_password(PASSWORD))

    def test_deactivated_record_cannot_be_claimed(self):
        code = self.otp()
        self.offline.is_active = False
        self.offline.save()
        self.assertError(self.complete(code), 400, "CLAIM_INVALID")

    def test_claim_writes_an_audit_row_and_security_log_without_secrets(self):
        code = self.otp()
        with self.assertLogs("apps.security", level="INFO") as logs:
            self.complete(code)
        self.assertIn("claim.completed", [r.getMessage() for r in logs.records])
        row = AuditLog.objects.get(action="account.claimed")
        self.assertEqual(row.entity_id, self.offline.pk)
        self.assertEqual(row.actor_id, self.offline.pk)
        self.assertNotIn(code, str(row.changes) + row.reason)
        self.assertNotIn(NEW_PASSWORD, str(row.changes) + row.reason)

    def test_failures_are_logged_without_the_code(self):
        self.otp()
        with self.assertLogs("apps.security", level="WARNING") as logs:
            self.complete("999999")
        record = logs.records[0]
        self.assertEqual(record.getMessage(), "claim.failed")
        self.assertNotIn("999999", str(vars(record)))

    def test_complete_requires_the_frontend_origin_and_json(self):
        self.client.credentials(HTTP_ORIGIN="https://evil.example")
        self.assertError(self.complete("123456"), 403, "ORIGIN_NOT_ALLOWED")
        self.client.credentials()  # no Origin header at all
        self.assertError(self.complete("123456"), 403, "ORIGIN_NOT_ALLOWED")

    def test_ten_completions_per_minute_per_ip(self):
        # Distinct phones, so the per-phone lock-out does not interfere with the per-IP limit.
        for n in range(10):
            self.assertEqual(self.complete("123456", phone=f"98111 0{n:04d}").status_code, 400)
        self.assertError(self.complete("123456", phone="9811100998"), 429, "RATE_LIMITED")

    def test_validation_errors(self):
        self.assertError(self.complete("123456", phone="123"), 400, "VALIDATION_ERROR")
        self.assertError(self.post("claim/complete/", {"phone": PHONE_INPUT}), 400, "VALIDATION_ERROR")


class OwnerClaimCodeTests(ClaimTestCase):
    def test_code_is_eight_unambiguous_characters_hashed_and_valid_seven_days(self):
        code, claim = claims.issue_claim_code(student=self.offline, issued_by=self.owner)
        self.assertRegex(code, r"^[A-HJKMNP-Z2-9]{8}$")
        stored = AccountClaim.objects.get(pk=claim.pk)
        self.assertNotIn(code, stored.code_hash)
        self.assertTrue(check_password(code, stored.code_hash))
        self.assertEqual(stored.issued_by, self.owner)
        self.assertAlmostEqual((stored.expires_at - timezone.now()).total_seconds(), 7 * 86400, delta=10)

    def test_issuing_again_revokes_the_previous_code(self):
        first = self.owner_code()
        second = self.owner_code()
        self.assertEqual(AccountClaim.objects.filter(channel="owner_code", status="revoked").count(), 1)
        self.assertError(self.complete(first), 400, "CLAIM_INVALID")
        self.assertEqual(self.complete(second).status_code, 200)

    def test_issuing_is_audited_without_the_code(self):
        code, _ = claims.issue_claim_code(student=self.offline, issued_by=self.owner)
        row = AuditLog.objects.get(action="claim.code_issued")
        self.assertEqual(row.actor_id, self.owner.pk)
        self.assertEqual(row.entity_id, self.offline.pk)
        self.assertNotIn(code, str(row.changes))

    def test_already_claimed_students_conflict(self):
        from apps.core.exceptions import Conflict

        code = self.owner_code()
        self.assertEqual(self.complete(code).status_code, 200)
        self.offline.refresh_from_db()
        with self.assertRaises(Conflict):
            claims.issue_claim_code(student=self.offline, issued_by=self.owner)
        online = make_student()
        with self.assertRaises(Conflict):
            claims.issue_claim_code(student=online, issued_by=self.owner)

    def test_only_owners_can_issue(self):
        from apps.core.exceptions import AppError

        with self.assertRaises(AppError):
            claims.issue_claim_code(student=self.offline, issued_by=make_student())


class RegistrationClaimRoundTripTests(ClaimTestCase):
    """Offline, then online signup: registration demands a claim, and the claim completes it (SECURITY.md 20)."""

    def test_register_with_the_offline_phone_requires_a_claim_then_the_claim_succeeds(self):
        response = self.register(name="Rahul S", email=EMAIL, phone=PHONE_INPUT)
        self.assertError(response, 409, "CLAIM_REQUIRED")
        self.assertEqual(response.json()["details"]["channels"], ["email_otp", "owner_code"])
        self.assertEqual(User.objects.filter(phone=PHONE).count(), 1)

        self.assertEqual(self.complete(self.otp()).status_code, 200)
        self.assertError(self.register(name="Rahul S", email=EMAIL, phone=PHONE_INPUT), 409, "EMAIL_TAKEN")

    def test_conflicting_phone_and_email_are_rejected_at_registration(self):
        make_student(email="other@example.com", phone="+919811100070")
        response = self.register(email="other@example.com", phone=PHONE_INPUT)
        self.assertError(response, 409, "IDENTITY_CONFLICT")


class ClaimConcurrencyTests(TransactionTestCase):
    """The same code used by two simultaneous requests succeeds exactly once."""

    def test_only_one_of_two_simultaneous_completions_succeeds(self):
        offline = make_offline()
        claims.start_claim(phone=PHONE, channel="email_otp")
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def worker(password: str):
            try:
                barrier.wait()
                claims.complete_claim(phone=PHONE, code=code, password=password)
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

        self.assertEqual(sorted(outcomes), ["ClaimInvalid", "ok"])
        offline.refresh_from_db()
        self.assertFalse(offline.is_offline)
        self.assertEqual(AccountClaim.objects.filter(user=offline, status="used").count(), 1)
        self.assertEqual(AuditLog.objects.filter(action="account.claimed").count(), 1)
