from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "student",
            "booking",
            "membership",
            "amount",
            "payment_method",
            "status",
            "razorpay_order_id",
            "razorpay_payment_id",
            "razorpay_signature",
            "transaction_id",
            "paid_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "student",
            "status",
            "razorpay_order_id",
            "razorpay_payment_id",
            "razorpay_signature",
            "transaction_id",
            "paid_at",
            "created_at",
            "updated_at",
        ]