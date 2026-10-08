"""Plain test-data factories (BACKEND_ARCHITECTURE.md section 15; no extra dependency)."""

import itertools

from django.contrib.auth import get_user_model

_seq = itertools.count(1)


def make_user(
    *,
    role: str = "student",
    email: str | None = None,
    name: str | None = None,
    password: str = "Str0ng-pass-123",
    phone: str | None = None,
    **extra,
):
    n = next(_seq)
    User = get_user_model()
    return User.objects.create_user(
        email=email if email is not None else f"user{n}@example.com",
        name=name or f"Test User {n}",
        password=password,
        role=role,
        phone=phone if phone is not None else f"+9190000{n:05d}",
        **extra,
    )


def make_owner(**kwargs):
    return make_user(role="owner", **kwargs)


def make_student(**kwargs):
    return make_user(role="student", **kwargs)
