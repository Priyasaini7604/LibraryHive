"""Attendance endpoints #62-#70 (BACKEND_ARCHITECTURE.md 9.9)."""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok

from . import selectors, serializers, services

STUDENT = [IsAuthenticated, IsStudent]
OWNER = [IsAuthenticated, IsOwner, HasLibrary]


def _reload(record):
    return selectors._base().get(pk=record.pk)


class StudentCheckInView(APIView):
    """#62: check in at a library where the student is a member."""

    permission_classes = STUDENT
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.CheckInInput, responses={201: None})
    def post(self, request):
        data = serializers.CheckInInput(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.check_in(student=request.user, library_id=data.validated_data["library_id"])
        return created(serializers.record_row(_reload(record)))


class StudentCheckOutView(APIView):
    """#63: close the student's open record."""

    permission_classes = STUDENT

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        record = services.check_out(student=request.user)
        return ok(serializers.record_row(_reload(record)))


class StudentAttendanceView(APIView):
    """#64: the student's own history with a summary."""

    permission_classes = STUDENT

    @extend_schema(parameters=[serializers.StudentHistoryQuery], responses={200: None})
    def get(self, request):
        query = serializers.StudentHistoryQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.student_records(request.user, month=query.validated_data.get("month"))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        response = paginator.get_paginated_response([serializers.record_row(r) for r in page])
        response.data["data"]["summary"] = selectors.summary(queryset)
        return response


class StudentCurrentView(APIView):
    """#65: is the student checked in right now?"""

    permission_classes = STUDENT

    @extend_schema(responses={200: None})
    def get(self, request):
        record = selectors.current_record(request.user)
        return ok(serializers.record_row(record) if record else None)


class OwnerLiveView(APIView):
    """#66: who is present now."""

    permission_classes = OWNER

    @extend_schema(responses={200: None})
    def get(self, request):
        return ok([serializers.live_row(r) for r in selectors.live_roster(request.user.library)])


class OwnerAttendanceView(APIView):
    """#67: the library's attendance history."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.OwnerHistoryQuery], responses={200: None})
    def get(self, request):
        query = serializers.OwnerHistoryQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        queryset = selectors.owner_records(
            request.user.library,
            date_=values.get("date"),
            date_from=values.get("from_"),
            date_to=values.get("to"),
            student_id=values.get("student_id"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response([serializers.owner_record_row(r) for r in page])


class OwnerCheckInView(APIView):
    """#68: check a member in by hand."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.OwnerCheckInInput, responses={201: None})
    def post(self, request):
        data = serializers.OwnerCheckInInput(data=request.data)
        data.is_valid(raise_exception=True)
        record = services.owner_check_in(
            library=request.user.library, owner=request.user, membership_id=data.validated_data["membership_id"]
        )
        return created(serializers.owner_record_row(_reload(record)))


class OwnerCheckOutView(APIView):
    """#69: close an open record by hand."""

    permission_classes = OWNER

    @extend_schema(request=None, responses={200: None})
    def post(self, request, record_id):
        record = services.owner_check_out(library=request.user.library, owner=request.user, record_id=record_id)
        return ok(serializers.owner_record_row(_reload(record)))


class OwnerCorrectionView(APIView):
    """#70: correct the times of a record."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.CorrectionInput, responses={200: None})
    def patch(self, request, record_id):
        data = serializers.CorrectionInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        record = services.correct_record(
            library=request.user.library,
            owner=request.user,
            record_id=record_id,
            reason=values["reason"],
            check_in_at=values.get("check_in_at"),
            check_out_at=values.get("check_out_at"),
        )
        return ok(serializers.owner_record_row(_reload(record)))
