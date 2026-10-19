"""Payment endpoints #41-#47 (BACKEND_ARCHITECTURE.md 9.7).

Renewal orders (#41 renewal part) and offline renewals (#48) belong to T15.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.core.pagination import StandardPagination
from apps.core.permissions import HasLibrary, IsOwner, IsStudent
from apps.core.responses import created, ok

from . import selectors, services
from .serializers import (
    CreateOrderInput,
    OwnerPaymentDetailSerializer,
    OwnerPaymentQuery,
    OwnerPaymentSerializer,
    PaymentSerializer,
    StudentQuery,
    StudentReceiptSerializer,
    VerifyInput,
)


class CreateOrderView(APIView):
    """#41: create the gateway order for the student's own live booking hold."""

    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [JSONParser]

    @extend_schema(request=CreateOrderInput, responses={201: None})
    def post(self, request):
        data = CreateOrderInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values.get("membership_id"):
            result = services.create_renewal_order(
                student=request.user, membership_id=values["membership_id"], plan_id=values["plan_id"]
            )
        else:
            result = services.create_order(student=request.user, hold_id=values["hold_id"])
        payment = result.payment
        user = request.user
        return created(
            {
                "payment_id": str(payment.pk),
                "gateway": "razorpay",
                "key_id": result.key_id,
                "order_id": result.order_id,
                "amount_paise": result.amount_paise,
                "currency": result.currency,
                "description": f"{payment.plan.name} at {payment.library.name}",
                "prefill": {"name": user.name, "email": user.email, "phone": user.phone},
            }
        )


class VerifyPaymentView(APIView):
    """#42: verify the checkout signature server-side, then confirm. Repeating the call is harmless."""

    permission_classes = [IsAuthenticated, IsStudent]
    parser_classes = [JSONParser]

    @extend_schema(request=VerifyInput, responses={200: None})
    def post(self, request):
        data = VerifyInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        result = services.verify_checkout(
            student=request.user,
            order_id=values["razorpay_order_id"],
            payment_id=values["razorpay_payment_id"],
            signature=values["razorpay_signature"],
        )
        payment, membership = result.payment, result.membership
        return ok(
            {
                "payment": {
                    "id": str(payment.pk),
                    "status": payment.status,
                    "receipt_number": payment.receipt_number,
                    "amount": str(payment.amount),
                    "period_start": payment.period_start,
                    "period_end": payment.period_end,
                },
                "membership": None
                if membership is None
                else {
                    "id": str(membership.pk),
                    "seat": {"id": str(membership.seat_id), "label": membership.seat.label},
                    "next_due_date": membership.next_due_date,
                    "status": _status(membership),
                },
            }
        )


def _status(membership) -> str:
    from apps.memberships import selectors as membership_selectors

    return membership_selectors.annotate_status(type(membership).objects.filter(pk=membership.pk)).get().status


class RazorpayWebhookView(APIView):
    """#43: the gateway's asynchronous confirmation. The signature is its only authentication.

    The raw body is read before anything parses it. No session or token is accepted, so Django's CSRF check
    does not apply. After a valid signature the answer is always 200.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    parser_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook"

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        result = services.handle_webhook(
            raw_body=request.body,
            signature=request.headers.get("X-Razorpay-Signature", ""),
            event_id=request.headers.get("X-Razorpay-Event-Id", ""),
        )
        _ = result  # the stored result is for operators; the gateway only needs the 200
        return ok({"status": "ok"})


class StudentPaymentListView(APIView):
    """#44: the student's payment history (also used by checkout to confirm after a dropped connection)."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(parameters=[StudentQuery], responses={200: PaymentSerializer(many=True)})
    def get(self, request):
        query = StudentQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.student_payments(request.user, order_id=query.validated_data.get("order_id"))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(PaymentSerializer(page, many=True).data)


class StudentPaymentDetailView(APIView):
    """#45: the receipt view of one of the student's own payments."""

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(responses={200: StudentReceiptSerializer})
    def get(self, request, payment_id):
        payment = selectors.student_payment(request.user, payment_id)
        if payment is None:
            raise NotFound()
        return ok(StudentReceiptSerializer(payment).data)


class OwnerPaymentListView(APIView):
    """#46: the library's payment ledger."""

    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]

    @extend_schema(parameters=[OwnerPaymentQuery], responses={200: OwnerPaymentSerializer(many=True)})
    def get(self, request):
        query = OwnerPaymentQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        queryset = selectors.owner_payments(request.user.library, **query.validated_data)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(OwnerPaymentSerializer(page, many=True).data)


class OwnerPaymentDetailView(APIView):
    """#47: one payment of the owner's library."""

    permission_classes = [IsAuthenticated, IsOwner, HasLibrary]

    @extend_schema(responses={200: OwnerPaymentDetailSerializer})
    def get(self, request, payment_id):
        payment = selectors.owner_payment(request.user.library, payment_id)
        if payment is None:
            raise NotFound()
        return ok(OwnerPaymentDetailSerializer(payment).data)
