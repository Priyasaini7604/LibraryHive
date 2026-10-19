"""Dashboard, report, export and activity-log endpoints #82-#89 (BACKEND_ARCHITECTURE.md 9.12)."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.attendance import selectors as attendance_selectors
from apps.core import audit
from apps.core.dates import business_today
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import ok
from apps.memberships import selectors as membership_selectors
from apps.payments import selectors as payment_selectors

from . import exports, selectors, serializers

OWNER = [IsAuthenticated, IsOwner, HasLibrary]


class OwnerDashboardView(APIView):
    """#82: the owner's KPI dashboard."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(selectors.owner_dashboard(request.user.library))


class OccupancyReportView(APIView):
    """#83: seat occupancy, overall and by row."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(selectors.occupancy_report(request.user.library))


class RevenueReportView(APIView):
    """#84: revenue from successful payments only."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.RevenueQuery], responses={200: None})
    def get(self, request):
        query = serializers.RevenueQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        return ok(selectors.revenue_report(request.user.library, values["from_"], values["to"]))


class ComplaintReportView(APIView):
    """#85: complaints by status and category."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.OptionalRangeQuery], responses={200: None})
    def get(self, request):
        query = serializers.OptionalRangeQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        return ok(
            selectors.complaint_report(request.user.library, date_from=values.get("from_"), date_to=values.get("to"))
        )


class DomainReportView(APIView):
    """#86: current members per exam domain."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(selectors.domain_report(request.user.library))


class _ExportView(APIView):
    """Base for the CSV downloads (#87): library-scoped, throttled, audited, streamed."""

    permission_classes = OWNER
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "export"
    kind = ""
    query_class = serializers.OptionalRangeQuery

    def build(self, library, values):  # pragma: no cover - overridden
        raise NotImplementedError

    @extend_schema(responses={200: None})
    def get(self, request):
        query = self.query_class(data=request.query_params)
        query.is_valid(raise_exception=True)
        library = request.user.library
        header, rows = self.build(library, query.validated_data)
        audit.record(
            actor=request.user,
            action=f"export.{self.kind}",
            entity_type="library",
            entity_id=library.pk,
            library=library,
            changes={key: str(value) for key, value in query.validated_data.items()},
        )
        return exports.stream_csv(f"{self.kind}-{business_today():%Y%m%d}.csv", header, rows)


class MembersExportView(_ExportView):
    kind = "members"
    query_class = serializers.MemberExportQuery

    def build(self, library, values):
        queryset = membership_selectors.library_members_for_export(library, status=values.get("status"))
        return exports.MEMBER_HEADER, exports.member_rows(queryset)


class PaymentsExportView(_ExportView):
    kind = "payments"

    def build(self, library, values):
        queryset = payment_selectors.library_payments_between(library, values.get("from_"), values.get("to"))
        return exports.PAYMENT_HEADER, exports.payment_rows(queryset)


class AttendanceExportView(_ExportView):
    kind = "attendance"

    def build(self, library, values):
        queryset = attendance_selectors.owner_records(library, date_from=values.get("from_"), date_to=values.get("to"))
        return exports.ATTENDANCE_HEADER, exports.attendance_rows(queryset)


class AuditLogView(APIView):
    """#88: the library's activity log."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.AuditQuery], responses={200: None})
    def get(self, request):
        query = serializers.AuditQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        queryset = selectors.audit_entries(
            request.user.library,
            action=values.get("action"),
            entity_type=values.get("entity_type"),
            date_from=values.get("from_"),
            date_to=values.get("to"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response([serializers.audit_row(e) for e in page])


class StudentDashboardView(APIView):
    """#89: the student's home."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok(serializers.student_dashboard_data(selectors.student_dashboard(request.user)))
