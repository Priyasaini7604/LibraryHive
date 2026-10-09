"""No endpoint may be public by accident (SECURITY.md section 5).

Every DRF view under /api/v1/ whose permission classes include AllowAny must be
listed here by URL name. Add a name only when SECURITY.md section 5 lists the
endpoint as public.
"""

from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

PUBLIC_ENDPOINTS = {
    "health",
    "meta-domains",
    "meta-amenities",
    "schema",  # public only when settings.SCHEMA_PUBLIC (non-production); see test_platform_views
}


def _api_views(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _api_views(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern):
            view_class = getattr(entry.callback, "cls", None)
            if view_class is not None and issubclass(view_class, APIView):
                yield prefix + str(entry.pattern), entry.name, view_class


class RouteInventoryTests(SimpleTestCase):
    def test_only_listed_endpoints_allow_anonymous_access(self):
        unexpected = []
        for route, name, view_class in _api_views(get_resolver().url_patterns):
            if not route.startswith("api/v1/"):
                continue
            if any(issubclass(p, AllowAny) for p in view_class.permission_classes) and name not in PUBLIC_ENDPOINTS:
                unexpected.append(f"{route} ({name})")
        self.assertEqual(unexpected, [], "Public endpoints not listed in SECURITY.md section 5")

    def test_listed_public_endpoints_exist(self):
        names = {name for _, name, _ in _api_views(get_resolver().url_patterns)}
        self.assertTrue(PUBLIC_ENDPOINTS <= names, PUBLIC_ENDPOINTS - names)

    def test_api_is_only_served_under_v1(self):
        for route, _, _ in _api_views(get_resolver().url_patterns):
            self.assertTrue(route.startswith("api/v1/"), route)
