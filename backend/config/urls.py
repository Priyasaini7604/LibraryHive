"""URL configuration. The API is served under /api/v1/ only (BACKEND_ARCHITECTURE.md section 3)."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("apps.core.urls")),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include(api_v1)),
]

if settings.DEBUG and settings.STORAGE_BACKEND == "local":
    # Local development only: serve public media (library photos) from disk.
    urlpatterns += static(f"{settings.MEDIA_URL}public/", document_root=settings.MEDIA_ROOT / "public")

handler404 = "apps.core.views.json_not_found"
handler500 = "apps.core.views.json_server_error"
