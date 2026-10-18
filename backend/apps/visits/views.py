"""Visit request endpoints #77-#81 (BACKEND_ARCHITECTURE.md 9.11)."""

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


def _page(request, queryset, row):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response([row(item) for item in page])


class StudentVisitListView(APIView):
    """#77 (request a visit) and #78 (own requests)."""

    permission_classes = STUDENT
    parser_classes = [JSONParser]

    @extend_schema(parameters=[serializers.StudentQuery], responses={200: None})
    def get(self, request):
        query = serializers.StudentQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.student_visits(request.user, status=query.validated_data.get("status"))
        return _page(request, queryset, serializers.student_row)

    @extend_schema(request=serializers.RequestVisitInput, responses={201: None})
    def post(self, request):
        data = serializers.RequestVisitInput(data=request.data)
        data.is_valid(raise_exception=True)
        visit = services.request_visit(student=request.user, **data.validated_data)
        return created(serializers.student_row(selectors.student_visits(request.user).get(pk=visit.pk)))


class StudentVisitCancelView(APIView):
    """#79: withdraw a pending request."""

    permission_classes = STUDENT

    @extend_schema(request=None, responses={200: None})
    def post(self, request, visit_id):
        visit = services.cancel_visit(student=request.user, visit_id=visit_id)
        return ok(serializers.student_row(selectors.student_visits(request.user).get(pk=visit.pk)))


class OwnerVisitListView(APIView):
    """#80: the owner's visit inbox."""

    permission_classes = OWNER

    @extend_schema(parameters=[serializers.OwnerQuery], responses={200: None})
    def get(self, request):
        query = serializers.OwnerQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        queryset = selectors.owner_visits(
            request.user.library,
            status=values.get("status"),
            date_from=values.get("from_"),
            date_to=values.get("to"),
        )
        return _page(request, queryset, serializers.owner_row)


class OwnerVisitDecisionView(APIView):
    """#81: accept or reject a pending request."""

    permission_classes = OWNER
    parser_classes = [JSONParser]

    @extend_schema(request=serializers.DecisionInput, responses={200: None})
    def post(self, request, visit_id):
        data = serializers.DecisionInput(data=request.data)
        data.is_valid(raise_exception=True)
        visit = services.decide(
            library=request.user.library,
            owner=request.user,
            visit_id=visit_id,
            decision=data.validated_data["decision"],
            owner_note=data.validated_data["owner_note"],
        )
        return ok(serializers.owner_row(selectors.owner_visits(request.user.library).get(pk=visit.pk)))
