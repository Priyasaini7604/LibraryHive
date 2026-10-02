from django.urls import path

from .views import (
    PaymentListCreateView,
    PaymentOrderCreateView,
    PaymentSuccessView,
    PaymentVerifyView,
    RenewalPaymentOrderCreateView,
    RenewalPaymentVerifyView,
)

urlpatterns = [
    path(
        "",
        PaymentListCreateView.as_view(),
        name="payment-list-create",
    ),

    path(
        "create-order/",
        PaymentOrderCreateView.as_view(),
        name="payment-create-order",
    ),

    path(
        "verify/",
        PaymentVerifyView.as_view(),
        name="payment-verify",
    ),

    path(
        "renewal/create-order/",
        RenewalPaymentOrderCreateView.as_view(),
        name="renewal-payment-create-order",
    ),

    path(
        "renewal/verify/",
        RenewalPaymentVerifyView.as_view(),
        name="renewal-payment-verify",
    ),

    path(
        "<uuid:payment_id>/success/",
        PaymentSuccessView.as_view(),
        name="payment-success",
    ),
]