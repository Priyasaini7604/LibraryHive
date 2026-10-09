"""Read-side queries for accounts."""

from dataclasses import dataclass

from .models import User


@dataclass(frozen=True)
class IdentityMatch:
    """Users matching a normalised email and phone, looked up separately (SPEC.md 4.6)."""

    by_email: User | None
    by_phone: User | None

    @property
    def conflicting(self) -> bool:
        """Email and phone belong to two different existing users."""
        return bool(self.by_email and self.by_phone and self.by_email.pk != self.by_phone.pk)


def find_identity(*, email: str | None, phone: str | None) -> IdentityMatch:
    """Look up by email and by phone independently. Names are never used for matching."""
    by_email = User.objects.filter(email=email).first() if email else None
    by_phone = User.objects.filter(phone=phone).first() if phone else None
    return IdentityMatch(by_email=by_email, by_phone=by_phone)
