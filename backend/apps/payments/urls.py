from django.urls import path

from . import views

urlpatterns = [
    path("payments/orders/", views.CreateOrderView.as_view(), name="payment-order-create"),
    path("payments/verify/", views.VerifyPaymentView.as_view(), name="payment-verify"),
    path("payments/webhook/razorpay/", views.RazorpayWebhookView.as_view(), name="payment-webhook-razorpay"),
    path("student/payments/", views.StudentPaymentListView.as_view(), name="student-payment-list"),
    path(
        "student/payments/<uuid:payment_id>/", views.StudentPaymentDetailView.as_view(), name="student-payment-detail"
    ),
    path("owner/payments/", views.OwnerPaymentListView.as_view(), name="owner-payment-list"),
    path("owner/payments/<uuid:payment_id>/", views.OwnerPaymentDetailView.as_view(), name="owner-payment-detail"),
]
