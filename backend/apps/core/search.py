"""Small helpers for owner-side list searches."""


def phone_digits(search: str) -> str:
    """The digits to match against phone numbers, or "" when the query is not a phone number.

    "98765 43210" and "+91-98765" are phone searches; "A-2" or "Asha 2" are not, so a seat label or a name that
    happens to contain a digit never matches every phone with that digit.
    """
    compact = search.replace(" ", "").replace("-", "").lstrip("+")
    return compact if compact.isdigit() and len(compact) >= 3 else ""
