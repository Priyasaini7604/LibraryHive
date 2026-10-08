"""Business dates (SPEC.md section 1): "today" is computed in Asia/Kolkata."""

from datetime import date, datetime

from django.utils import timezone


def business_now() -> datetime:
    """Current time in the business time zone (settings.TIME_ZONE)."""
    return timezone.localtime(timezone.now())


def business_today() -> date:
    return business_now().date()
