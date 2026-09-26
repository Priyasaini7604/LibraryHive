from django.urls import path

from .views import PaymentListCreateView, PaymentSuccessView


urlpatterns = [
    path("", PaymentListCreateView.as_view(), name="payment-list-create"),
    path(
        "<uuid:payment_id>/success/",
        PaymentSuccessView.as_view(),
        name="payment-success",
    ),
]