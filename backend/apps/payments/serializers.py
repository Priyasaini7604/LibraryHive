from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "student",
            "booking",
            "amount",
            "payment_method",
            "status",
            "transaction_id",
            "paid_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "student",
            "status",
            "transaction_id",
            "paid_at",
            "created_at",
            "updated_at",
        ]