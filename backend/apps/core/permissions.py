"""Role permissions (SECURITY.md section 5).

The role in the JWT is only a UI hint; these checks always use the user row
loaded from the database. Tenant scoping mixins and HasLibrary are added with
the Library model in T08.
"""

from rest_framework.permissions import BasePermission


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
