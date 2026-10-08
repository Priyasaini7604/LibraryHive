from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("meta/domains/", views.DomainListView.as_view(), name="meta-domains"),
    path("meta/amenities/", views.AmenityListView.as_view(), name="meta-amenities"),
    path("schema/", views.SchemaView.as_view(), name="schema"),
]
