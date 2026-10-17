from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("claim/start/", views.ClaimStartView.as_view(), name="auth-claim-start"),
    path("claim/complete/", views.ClaimCompleteView.as_view(), name="auth-claim-complete"),
    path("password-reset/request/", views.PasswordResetRequestView.as_view(), name="auth-password-reset-request"),
    path("password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]
