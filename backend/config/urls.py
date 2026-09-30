from django.contrib import admin
from django.urls import path, include


api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("libraries/", include("apps.libraries.urls")),
    path("seats/", include("apps.seats.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("payments/", include("apps.payments.urls")),
    path("memberships/", include("apps.memberships.urls")),
    path("notifications/", include("apps.notifications.urls")),
]


urlpatterns = [
    path("admin/", admin.site.urls),

    # Both /api/v1/ and /api/ are supported
    path("api/v1/", include(api_v1_patterns)),
    path("api/", include(api_v1_patterns)),
]