"""OpenAPI description of the custom bearer-token authentication (SECURITY.md section 4)."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.JWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
