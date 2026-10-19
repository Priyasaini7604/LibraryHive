"""Tenant scoping for views (ARCHITECTURE.md 12, SECURITY.md 6).

No view writes its own tenant filter. An object outside the caller's scope is
simply not found (404), so the existence of other tenants' IDs is never
confirmed.
"""

from django.http import Http404

from .exceptions import NotFound


class _ScopedMixin:
    model = None
    scope_field: str
    scope_label = "resource"

    def get_scope(self):
        raise NotImplementedError

    def get_queryset(self):
        if self.model is None:
            raise NotImplementedError("Set `model` on the view.")
        return self.model.objects.filter(**{self.scope_field: self.get_scope()})

    def get_scoped_object(self, **lookup):
        try:
            return self.get_queryset().get(**lookup)
        except (self.model.DoesNotExist, ValueError, Http404) as exc:
            raise NotFound() from exc


class OwnerLibraryScopedMixin(_ScopedMixin):
    """Rows of `model` that belong to the signed-in owner's library."""

    scope_field = "library"

    def get_scope(self):
        return self.request.user.library


class StudentOwnedScopedMixin(_ScopedMixin):
    """Rows of `model` that belong to the signed-in student."""

    scope_field = "student"

    def get_scope(self):
        return self.request.user
