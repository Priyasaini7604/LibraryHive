"""Phone normalisation (SPEC.md section 1): every phone is stored as E.164.

Only Indian numbers are accepted in the MVP (UI_ARCHITECTURE.md 7).
"""

import phonenumbers

DEFAULT_REGION = "IN"
_ACCEPTED_TYPES = {
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
}


class InvalidPhone(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    """'98765 43210', '+91-98765-43210', '09876543210' -> '+919876543210'."""
    if not raw or not raw.strip():
        raise InvalidPhone("Enter a phone number.")
    try:
        number = phonenumbers.parse(raw.strip(), DEFAULT_REGION)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhone("Enter a valid Indian mobile number.") from exc
    if (
        phonenumbers.region_code_for_number(number) != DEFAULT_REGION
        or not phonenumbers.is_valid_number(number)
        or phonenumbers.number_type(number) not in _ACCEPTED_TYPES
    ):
        raise InvalidPhone("Enter a valid Indian mobile number.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def mask_email(email: str | None) -> str | None:
    """'rahul.sharma@gmail.com' -> 'r***@gmail.com' (shown to confirm identity, never in full)."""
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"
