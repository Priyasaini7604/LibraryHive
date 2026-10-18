"""Input validation and output shapes for payments. No side effects here."""

from rest_framework import serializers

from .models import Payment


class CreateOrderInput(serializers.Serializer):
    """#41 (new booking): only the hold. The amount is never accepted from the client."""

    hold_id = serializers.UUIDField()


class VerifyInput(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=64)
    razorpay_payment_id = serializers.CharField(max_length=64)
    razorpay_signature = serializers.CharField(max_length=256)


class OwnerPaymentQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=Payment.Status.choices, required=False)
    method = serializers.ChoiceField(choices=Payment.Method.choices, required=False)
    channel = serializers.ChoiceField(choices=Payment.Channel.choices, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)


class StudentQuery(serializers.Serializer):
    order_id = serializers.CharField(max_length=64, required=False, allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    """#44: one row of the student's payment history."""

    library = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "library",
            "purpose",
            "method",
            "amount",
            "status",
            "receipt_number",
            "period_start",
            "period_end",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_library(self, payment) -> dict:
        return {"id": str(payment.library_id), "name": payment.library.name}


def _seat_label(payment: Payment) -> str | None:
    seat = payment.membership.seat if payment.membership_id else (payment.hold.seat if payment.hold_id else None)
    return seat.label if seat else None


class StudentReceiptSerializer(PaymentSerializer):
    """#45: the receipt view: the payment plus library contact, plan name and seat label."""

    class Meta(PaymentSerializer.Meta):
        fields = [*PaymentSerializer.Meta.fields, "library_contact", "plan_name", "seat_label"]
        read_only_fields = fields

    library_contact = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    seat_label = serializers.SerializerMethodField()

    def get_library_contact(self, payment) -> dict:
        library = payment.library
        return {"phone": library.contact_phone, "email": library.contact_email, "address": library.address}

    def get_plan_name(self, payment) -> str:
        return payment.plan.name

    def get_seat_label(self, payment) -> str | None:
        return _seat_label(payment)


class OwnerPaymentSerializer(PaymentSerializer):
    """#46: a ledger row with the student and, for offline entries, who recorded it."""

    student = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()

    class Meta(PaymentSerializer.Meta):
        fields = [*PaymentSerializer.Meta.fields, "channel", "student", "recorded_by"]
        read_only_fields = fields

    def get_student(self, payment) -> dict:
        student = payment.student
        return {"id": str(student.pk), "name": student.name, "phone": student.phone}

    def get_recorded_by(self, payment) -> dict | None:
        return {"name": payment.recorded_by.name} if payment.recorded_by_id else None


class OwnerPaymentDetailSerializer(OwnerPaymentSerializer):
    """#47: the ledger row plus plan, seat and failure details. Gateway secrets never appear."""

    plan_name = serializers.SerializerMethodField()
    seat_label = serializers.SerializerMethodField()

    class Meta(OwnerPaymentSerializer.Meta):
        fields = [*OwnerPaymentSerializer.Meta.fields, "plan_name", "seat_label", "failure_reason", "notes"]
        read_only_fields = fields

    def get_plan_name(self, payment) -> str:
        return payment.plan.name

    def get_seat_label(self, payment) -> str | None:
        return _seat_label(payment)
