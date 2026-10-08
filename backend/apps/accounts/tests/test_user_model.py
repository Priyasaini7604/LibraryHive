"""User model invariants enforced by the database (SPEC.md 3.1)."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import Domain
from apps.core.tests.factories import make_student


class UserModelTests(TestCase):
    def test_email_is_stored_trimmed_and_lowercased(self):
        user = make_student(email="  Rahul.Sharma@Gmail.COM ")
        user.refresh_from_db()
        self.assertEqual(user.email, "rahul.sharma@gmail.com")

    def test_email_is_unique_case_insensitively(self):
        make_student(email="dup@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_student(email="DUP@example.com")

    def test_phone_is_unique(self):
        make_student(phone="+919876543210")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_student(phone="+919876543210")

    def test_phone_must_be_e164(self):
        user = make_student()
        user.phone = "98765 43210"
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_offline_user_must_be_a_student(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email=None, name="Offline Owner", role="owner", is_offline=True, phone="+919811100000"
            )

    def test_offline_student_may_have_no_email_and_no_password(self):
        user = User.objects.create_user(
            email=None, name="Walk-in", role="student", is_offline=True, phone="+919811100001"
        )
        self.assertIsNone(user.email)
        self.assertFalse(user.has_usable_password())

    def test_online_account_requires_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(name="No Email", role="student", phone="+919811100002")

    def test_role_must_be_owner_or_student(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(name="Bad", email="bad@example.com", role="admin")

    def test_domain_reference_survives_vocabulary_retirement(self):
        upsc = Domain.objects.get(code="upsc")
        user = make_student(domain=upsc)
        upsc.is_active = False
        upsc.save()
        user.refresh_from_db()
        self.assertEqual(user.domain, upsc)

    def test_superuser_is_staff(self):
        admin = User.objects.create_superuser("admin@example.com", "Admin", "Str0ng-pass-123")
        self.assertTrue(admin.is_staff and admin.is_superuser)
