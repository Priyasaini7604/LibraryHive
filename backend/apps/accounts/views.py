"""Auth and profile endpoints (BACKEND_ARCHITECTURE.md #6-#11, SEC-1)."""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.responses import created, error_response, ok

from . import claims, password_reset, services, tokens
from .cookies import (
    FrontendOriginRequired,
    JsonRequestRequired,
    clear_refresh_cookie,
    read_refresh_cookie,
    set_refresh_cookie,
)
from .serializers import (
    AccessTokenOutput,
    AuthOutput,
    ClaimCompleteInput,
    ClaimStartInput,
    ClaimStartOutput,
    LoginInput,
    MessageOutput,
    PasswordResetConfirmInput,
    PasswordResetRequestInput,
    ProfileUpdateInput,
    RegisterInput,
    UserSerializer,
)
from .throttles import ClaimStartIdentityThrottle, LoginEmailThrottle, PasswordResetEmailThrottle

security_logger = logging.getLogger("apps.security")


def _auth_payload(result: services.AuthResult) -> dict:
    return {"access": result.tokens.access, "user": UserSerializer(result.user).data}


class RegisterView(APIView):
    """#6: register an owner or student; signs the new account in."""

    authentication_classes: list = []
    permission_classes = [AllowAny, FrontendOriginRequired, JsonRequestRequired]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(request=RegisterInput, responses={201: AuthOutput})
    def post(self, request):
        data = RegisterInput(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.register(**data.validated_data)
        response = created(_auth_payload(result))
        set_refresh_cookie(response, result.tokens.refresh)
        return response


class LoginView(APIView):
    """#7: email + password login. Generic error for every failure."""

    authentication_classes: list = []
    permission_classes = [AllowAny, FrontendOriginRequired, JsonRequestRequired]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle, LoginEmailThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginInput, responses={200: AuthOutput})
    def post(self, request):
        data = LoginInput(data=request.data)
        data.is_valid(raise_exception=True)
        result = services.login(**data.validated_data, request=request)
        response = ok(_auth_payload(result))
        set_refresh_cookie(response, result.tokens.refresh)
        return response


class RefreshView(APIView):
    """#8: rotate the refresh cookie and return a new access token."""

    authentication_classes: list = []
    permission_classes = [AllowAny, FrontendOriginRequired, JsonRequestRequired]
    parser_classes = [JSONParser]

    @extend_schema(request=None, responses={200: AccessTokenOutput})
    def post(self, request):
        try:
            pair = tokens.rotate(read_refresh_cookie(request))
        except tokens.TokenInvalid as exc:
            security_logger.info("auth.refresh_failed")
            response = error_response(status=exc.status, code=exc.code, message=exc.message)
            clear_refresh_cookie(response)
            return response
        response = ok({"access": pair.access})
        set_refresh_cookie(response, pair.refresh)
        return response


class LogoutView(APIView):
    """#9: blacklist the refresh cookie and clear it. Idempotent."""

    permission_classes = [IsAuthenticated, FrontendOriginRequired, JsonRequestRequired]
    parser_classes = [JSONParser]

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        tokens.revoke(read_refresh_cookie(request), user=request.user)
        security_logger.info("auth.logout")
        response = ok({})
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    """#10 (GET) and #11 (PATCH): the current user's profile."""

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return ok(UserSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateInput, responses={200: UserSerializer})
    def patch(self, request):
        data = ProfileUpdateInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        user = services.update_profile(
            request.user,
            name=values.get("name"),
            phone=values.get("phone"),
            domain_code=values.get("domain_code") or None,
            domain_provided="domain_code" in values,
        )
        return ok(UserSerializer(user).data)


class PasswordResetRequestView(APIView):
    """#13a: email a reset code. The response is identical for every email."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle, PasswordResetEmailThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestInput, responses={200: MessageOutput})
    def post(self, request):
        data = PasswordResetRequestInput(data=request.data)
        data.is_valid(raise_exception=True)
        return ok({"message": password_reset.request_password_reset(email=data.validated_data["email"])})


class PasswordResetConfirmView(APIView):
    """#13b: set a new password with the emailed code. Issues no tokens."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmInput, responses={200: MessageOutput})
    def post(self, request):
        data = PasswordResetConfirmInput(data=request.data)
        data.is_valid(raise_exception=True)
        return ok({"message": password_reset.confirm_password_reset(**data.validated_data)})


class ClaimStartView(APIView):
    """#12: begin claiming an offline account. Neutral response for every phone."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle, ClaimStartIdentityThrottle]
    throttle_scope = "claim_start"

    @extend_schema(request=ClaimStartInput, responses={200: ClaimStartOutput})
    def post(self, request):
        data = ClaimStartInput(data=request.data)
        data.is_valid(raise_exception=True)
        return ok(claims.start_claim(**data.validated_data))


class ClaimCompleteView(APIView):
    """#13: finish the claim, set a password and sign in (sets the refresh cookie)."""

    authentication_classes: list = []
    permission_classes = [AllowAny, FrontendOriginRequired, JsonRequestRequired]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "claim_complete"

    @extend_schema(request=ClaimCompleteInput, responses={200: AuthOutput})
    def post(self, request):
        data = ClaimCompleteInput(data=request.data)
        data.is_valid(raise_exception=True)
        result = claims.complete_claim(**data.validated_data)
        response = ok(_auth_payload(result))
        set_refresh_cookie(response, result.tokens.refresh)
        return response
