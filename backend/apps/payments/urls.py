from django.urls import path

from . import upi_views, views

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
    # Direct UPI payments with manual owner approval (UPI-01 to UPI-12).
    path("owner/payment-settings/", upi_views.OwnerPaymentSettingsView.as_view(), name="owner-payment-settings"),
    path("owner/payment-settings/qr/", upi_views.OwnerPaymentQrView.as_view(), name="owner-payment-qr"),
    path("owner/upi-payments/", upi_views.OwnerUpiRequestListView.as_view(), name="owner-upi-list"),
    path("owner/upi-payments/summary/", upi_views.OwnerUpiSummaryView.as_view(), name="owner-upi-summary"),
    path(
        "owner/upi-payments/<uuid:request_id>/", upi_views.OwnerUpiRequestDetailView.as_view(), name="owner-upi-detail"
    ),
    path(
        "owner/upi-payments/<uuid:request_id>/approve/",
        upi_views.OwnerUpiApproveView.as_view(),
        name="owner-upi-approve",
    ),
    path(
        "owner/upi-payments/<uuid:request_id>/reject/", upi_views.OwnerUpiRejectView.as_view(), name="owner-upi-reject"
    ),
    path(
        "owner/upi-payments/<uuid:request_id>/screenshot/",
        upi_views.OwnerUpiScreenshotView.as_view(),
        name="owner-upi-screenshot",
    ),
    path(
        "student/libraries/<uuid:library_id>/upi-info/",
        upi_views.StudentPaymentInfoView.as_view(),
        name="student-upi-info",
    ),
    path("student/upi-payments/", upi_views.StudentUpiRequestListView.as_view(), name="student-upi-list"),
    path(
        "student/upi-payments/<uuid:request_id>/",
        upi_views.StudentUpiRequestDetailView.as_view(),
        name="student-upi-detail",
    ),
    path(
        "student/upi-payments/<uuid:request_id>/cancel/",
        upi_views.StudentUpiRequestCancelView.as_view(),
        name="student-upi-cancel",
    ),
    path(
        "student/upi-payments/<uuid:request_id>/screenshot/",
        upi_views.StudentUpiScreenshotView.as_view(),
        name="student-upi-screenshot",
    ),
]
