from django.contrib import admin
from django.urls import path, include

api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("libraries/", include("apps.libraries.urls")),
    path("seats/", include("apps.seats.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # Both /api/v1/ and /api/ are supported for maximum compatibility
    path("api/v1/", include(api_v1_patterns)),
    path("api/", include(api_v1_patterns)),
]
