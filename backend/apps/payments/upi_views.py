"""Direct UPI payment endpoints (SPEC.md 3.11b-c; paths in BACKEND_ARCHITECTURE.md 9.7b).

Views stay thin: parse, permission, service, envelope. Every owner endpoint is scoped to the owner's own library
(another library's request is a 404); every student endpoint to the student's own rows.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok
from apps.core.storage import PRIVATE_FILE_SECONDS, private_file_url

from . import upi_selectors as selectors
from . import upi_serializers as out
from . import upi_services as services

OWNER = [IsAuthenticated, IsOwner, HasLibrary]
STUDENT = [IsAuthenticated, IsStudent]


class _PostThrottled(APIView):
    """Only writes use the stricter bucket; reads stay on the normal per-user limit."""

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method in ("POST", "PUT", "PATCH") else super().get_throttles()


class OwnerPaymentSettingsView(_PostThrottled):
    """GET the library's UPI settings, PATCH the UPI ID, instructions and the on/off switch."""

    permission_classes = OWNER
    parser_classes = [JSONParser]
    throttle_scope = "upload"

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(out.settings_data(selectors.settings_for(request.user.library), request=request))

    @extend_schema(request=out.PaymentSettingsInput, responses={200: None})
    def patch(self, request):
        data = out.PaymentSettingsInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.update_settings(library=request.user.library, actor=request.user, data=data.validated_data)
        return ok(out.settings_data(row, request=request))


class OwnerPaymentQrView(_PostThrottled):
    """POST upload or replace the QR (multipart); DELETE removes it."""

    permission_classes = OWNER
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "upload"

    @extend_schema(request={"multipart/form-data": out.QrUploadInput}, responses={200: None})
    def post(self, request):
        data = out.QrUploadInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.set_qr(
            library=request.user.library, actor=request.user, uploaded_file=data.validated_data["image"]
        )
        return ok(out.settings_data(row, request=request))

    @extend_schema(responses={200: None})
    def delete(self, request):
        row = services.remove_qr(library=request.user.library, actor=request.user)
        return ok(out.settings_data(row, request=request))


class StudentPaymentInfoView(APIView):
    """The library's QR, UPI ID and instructions, only for a student who is paying it now (404 otherwise)."""

    permission_classes = STUDENT

    @extend_schema(responses={200: None})
    def get(self, request, library_id):
        found = selectors.payment_info_for_student(request.user, library_id)
        if found is None:
            raise NotFound()
        library, row = found
        return ok(out.payment_info_data(library, row, request=request))


class StudentUpiRequestListView(_PostThrottled):
    """POST submit a UTR (multipart: an optional screenshot); GET the student's own requests."""

    permission_classes = STUDENT
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "upi_submit"

    @extend_schema(operation_id="student_upi_payments_list", responses={200: None})
    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(selectors.student_requests(request.user), request)
        return paginator.get_paginated_response([out.student_request_data(item) for item in page])

    @extend_schema(request={"multipart/form-data": out.SubmitInput}, responses={201: None})
    def post(self, request):
        data = out.SubmitInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        upi_request = services.submit_request(
            student=request.user,
            hold_id=values.get("hold_id"),
            membership_id=values.get("membership_id"),
            plan_id=values.get("plan_id"),
            utr=values["utr"],
            note=values.get("note", ""),
            screenshot=values.get("screenshot"),
        )
        return created(out.student_request_data(selectors.student_request(request.user, upi_request.pk)))


class StudentUpiRequestDetailView(APIView):
    permission_classes = STUDENT

    @extend_schema(operation_id="student_upi_payments_detail", responses={200: None})
    def get(self, request, request_id):
        item = selectors.student_request(request.user, request_id)
        if item is None:
            raise NotFound()
        return ok(out.student_request_data(item))


class StudentUpiRequestCancelView(APIView):
    permission_classes = STUDENT
    parser_classes = [JSONParser]

    @extend_schema(request=None, responses={200: None})
    def post(self, request, request_id):
        services.cancel_request(student=request.user, request_id=request_id)
        return ok(out.student_request_data(selectors.student_request(request.user, request_id)))


class StudentUpiScreenshotView(APIView):
    """A short-lived link to the student's own screenshot."""

    permission_classes = STUDENT

    @extend_schema(responses={200: None})
    def get(self, request, request_id):
        item = selectors.student_request(request.user, request_id)
        if item is None or not item.screenshot_key:
            raise NotFound()
        return ok({"url": private_file_url(item.screenshot_key, request=request), "expires_in": PRIVATE_FILE_SECONDS})


class OwnerUpiRequestListView(APIView):
    permission_classes = OWNER

    @extend_schema(operation_id="owner_upi_payments_list", parameters=[out.DecisionStatusQuery], responses={200: None})
    def get(self, request):
        query = out.DecisionStatusQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.owner_requests(request.user.library, status=query.validated_data.get("status"))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response([out.owner_request_data(item) for item in page])


class OwnerUpiSummaryView(APIView):
    """The number of requests waiting for the owner (for the navigation badge)."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(selectors.pending_summary(request.user.library))


class OwnerUpiRequestDetailView(APIView):
    permission_classes = OWNER

    @extend_schema(operation_id="owner_upi_payments_detail", responses={200: None})
    def get(self, request, request_id):
        item = selectors.owner_request(request.user.library, request_id)
        if item is None:
            raise NotFound()
        return ok(out.owner_request_data(item))


class OwnerUpiApproveView(APIView):
    """Approve after checking the real UPI or bank history. Activates the membership in one transaction."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=out.ApproveInput, responses={200: None})
    def post(self, request, request_id):
        data = out.ApproveInput(data=request.data)
        data.is_valid(raise_exception=True)
        library = request.user.library
        services.approve_request(
            library=library, owner=request.user, request_id=request_id, seat_id=data.validated_data.get("seat_id")
        )
        return ok(out.owner_request_data(selectors.owner_request(library, request_id)))


class OwnerUpiRejectView(APIView):
    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=out.RejectInput, responses={200: None})
    def post(self, request, request_id):
        data = out.RejectInput(data=request.data)
        data.is_valid(raise_exception=True)
        library = request.user.library
        services.reject_request(
            library=library, owner=request.user, request_id=request_id, reason=data.validated_data["reason"]
        )
        return ok(out.owner_request_data(selectors.owner_request(library, request_id)))


class OwnerUpiScreenshotView(APIView):
    """A short-lived link to the screenshot of a request in the owner's own library."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request, request_id):
        item = selectors.owner_request(request.user.library, request_id)
        if item is None or not item.screenshot_key:
            raise NotFound()
        return ok({"url": private_file_url(item.screenshot_key, request=request), "expires_in": PRIVATE_FILE_SECONDS})
