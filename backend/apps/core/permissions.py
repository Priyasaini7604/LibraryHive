"""Role permissions and tenant checks (SECURITY.md section 5).

The role in the JWT is only a UI hint; these checks always use the user row
loaded from the database.
"""

from rest_framework.permissions import BasePermission

from .exceptions import Conflict


class IsOwner(BasePermission):
    message = "Only library owners can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "owner")


class IsStudent(BasePermission):
    message = "Only students can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "student")


class IsPlatformAdmin(BasePermission):
    """LibraryHive team only: an active Django superuser with staff access (the same people who use Django admin).

    There is no platform-admin role in `User.Role`; owners and students can never satisfy this, whatever
    their JWT `role` claim says, because the flags are read from the database row.
    """

    message = "Only the LibraryHive team can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


class HasLibrary(BasePermission):
    """The owner has finished onboarding step 1; otherwise 409 LIBRARY_REQUIRED (not 403).

    Combine with `IsOwner`: a student never reaches this check as a 409.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.role == "owner"):
            return False
        if getattr(user, "library", None) is None:
            raise Conflict("Finish setting up your library first.", code="LIBRARY_REQUIRED")
        return True
