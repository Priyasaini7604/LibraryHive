from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Allows access only to authenticated users with the 'owner' role.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "role", None) == "owner"
        )


class IsStudent(permissions.BasePermission):
    """
    Allows access only to authenticated users with the 'student' role.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, "role", None) == "student"
        )


class IsLibraryOwnerOf(permissions.BasePermission):
    """
    Object-level permission to only allow the owner of the library (or related entity)
    to modify it. SAFE_METHODS are allowed if permitted by the view.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not (request.user and request.user.is_authenticated):
            return False

        # If the object itself is a Library
        if hasattr(obj, "owner"):
            return obj.owner == request.user

        # If the object is related to a Library (e.g. Seat, PricingPlan)
        if hasattr(obj, "library"):
            return getattr(obj.library, "owner", None) == request.user

        return False
