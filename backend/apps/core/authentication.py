"""JWT bearer authentication that also records the user in the log context."""

from rest_framework_simplejwt.authentication import JWTAuthentication as SimpleJWTAuthentication

from .context import set_user_context


class JWTAuthentication(SimpleJWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            set_user_context(result[0])
        return result
