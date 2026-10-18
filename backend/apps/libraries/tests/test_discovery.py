"""Public discovery list and explore page (#14, #15)."""

from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.tests.factories import make_owner
from apps.libraries import services

from .base import LibraryTestCase, make_library, make_plan

PRAYAGRAJ = (25.4358, 81.8463)


def published(name, lat, lng, *, price="1200.00", city="Prayagraj", domains=("upsc",), amenities=("wifi",)):
    library = make_library(
        make_owner(),
        name=name,
        latitude=lat,
        longitude=lng,
        city=city,
        domain_codes=list(domains),
        amenity_codes=list(amenities),
    )
    with mock.patch("apps.libraries.selectors.active_seat_count", return_value=1):
        make_plan(library, price=Decimal(price))
        services.refresh_publish_state(library)
    library.refresh_from_db()
    assert library.is_published
    return library


class DiscoveryTests(LibraryTestCase):
    def setUp(self):
        super().setUp()
        # Plan changes re-evaluate the publish rule, which needs an active seat (T10 provides the real count).
        patcher = mock.patch("apps.libraries.selectors.active_seat_count", return_value=1)
        patcher.start()
        self.addCleanup(patcher.stop)

    def list(self, **params):
        response = self.client.get(self.api("libraries/"), params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]

    def names(self, **params):
        return [item["name"] for item in self.list(**params)["items"]]

    def test_anonymous_sees_only_published_active_libraries(self):
        published("Live One", *PRAYAGRAJ)
        make_library(make_owner(), name="Draft")
        hidden = published("Hidden", *PRAYAGRAJ)
        type(hidden).objects.filter(pk=hidden.pk).update(is_active=False)
        self.assertEqual(self.names(), ["Live One"])

    def test_list_shape_and_pagination_envelope(self):
        published("Live One", *PRAYAGRAJ, price="900.00")
        data = self.list()
        self.assertEqual({"items", "page", "page_size", "total"}, set(data))
        item = data["items"][0]
        self.assertEqual(item["starting_price"], "900.00")
        self.assertEqual(item["domains"], ["upsc"])
        self.assertEqual(item["amenities"], ["wifi"])
        self.assertEqual(item["seat_counts"], {"total": 0, "empty": 0, "reserved": 0, "occupied": 0})
        self.assertNotIn("distance_km", item)
        self.assertNotIn("contact_email", item)

    def test_starting_price_is_cheapest_active_plan(self):
        library = published("Live One", *PRAYAGRAJ, price="1500.00")
        cheap = make_plan(library, name="Cheap", price=Decimal("700.00"))
        make_plan(library, name="Mid", price=Decimal("1000.00"))
        services.deactivate_plan(library=library, plan=cheap, actor=library.owner)
        self.assertEqual(self.list()["items"][0]["starting_price"], "1000.00")

    def test_search_domain_and_amenity_filters(self):
        published("Alpha Hive", *PRAYAGRAJ, domains=("upsc",), amenities=("wifi", "ac"))
        published("Beta Hive", *PRAYAGRAJ, domains=("neet",), amenities=("wifi",), city="Lucknow")
        self.assertEqual(self.names(search="alpha"), ["Alpha Hive"])
        self.assertEqual(self.names(search="lucknow"), ["Beta Hive"])
        self.assertEqual(self.names(domain="neet"), ["Beta Hive"])
        self.assertEqual(self.names(amenity="wifi"), ["Alpha Hive", "Beta Hive"])
        response = self.client.get(self.api("libraries/?amenity=wifi&amenity=ac"))
        self.assertEqual([i["name"] for i in response.json()["data"]["items"]], ["Alpha Hive"])

    def test_radius_filter_and_distance_sort(self):
        published("Near", 25.4400, 81.8500)
        published("Mid", 25.4600, 81.8700)
        published("Far", 26.8467, 80.9462)  # Lucknow, ~200 km
        self.assertEqual(self.names(lat=PRAYAGRAJ[0], lng=PRAYAGRAJ[1]), ["Near", "Mid"])
        wide = self.list(lat=PRAYAGRAJ[0], lng=PRAYAGRAJ[1], radius_km=50, sort="distance")["items"]
        self.assertEqual([i["name"] for i in wide], ["Near", "Mid"])
        self.assertLess(wide[0]["distance_km"], wide[1]["distance_km"])
        self.assertLess(wide[1]["distance_km"], 6)
        tight = self.list(lat=PRAYAGRAJ[0], lng=PRAYAGRAJ[1], radius_km=1)["items"]
        self.assertEqual([i["name"] for i in tight], ["Near"])

    def test_sort_by_price(self):
        published("Pricey", *PRAYAGRAJ, price="2000.00")
        published("Cheap", *PRAYAGRAJ, price="500.00")
        self.assertEqual(self.names(sort="price"), ["Cheap", "Pricey"])

    def test_query_validation(self):
        for params in [
            {"lat": 25.4},
            {"lng": 81.8},
            {"lat": 95, "lng": 81},
            {"sort": "distance"},
            {"radius_km": 51, "lat": 25, "lng": 81},
            {"sort": "bogus"},
        ]:
            response = self.client.get(self.api("libraries/"), params)
            self.assertEqual(response.status_code, 400, params)

    def test_query_count_does_not_grow_per_library(self):
        published("L1", *PRAYAGRAJ)
        with CaptureQueriesContext(connection) as one:
            self.list()
        for n in range(2, 7):
            published(f"L{n}", *PRAYAGRAJ)
        with CaptureQueriesContext(connection) as many:
            self.list()
        self.assertEqual(len(one), len(many))

    def test_detail_shape(self):
        library = published("Live One", *PRAYAGRAJ)
        inactive = make_plan(library, name="Retired", price=Decimal("100.00"))
        services.deactivate_plan(library=library, plan=inactive, actor=library.owner)
        response = self.client.get(self.api(f"libraries/{library.pk}/"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([p["name"] for p in data["plans"]], ["Monthly"])
        self.assertEqual(set(data["plans"][0]), {"id", "name", "duration_days", "price", "timing_note"})
        self.assertEqual({a["code"] for a in data["amenities"]}, {"wifi"})
        self.assertNotIn("domain_breakdown", data)  # added by T23, never faked
        self.assertEqual(data["seat_counts"], {"total": 0, "empty": 0, "reserved": 0, "occupied": 0})
        self.assertNotIn("owner", data)
        self.assertNotIn("is_published", data)

    def test_detail_404_for_unpublished_inactive_and_unknown(self):
        draft = make_library(make_owner())
        hidden = published("Hidden", *PRAYAGRAJ)
        type(hidden).objects.filter(pk=hidden.pk).update(is_active=False)
        for library_id in (draft.pk, hidden.pk, "00000000-0000-0000-0000-000000000000"):
            self.assertEqual(self.client.get(self.api(f"libraries/{library_id}/")).status_code, 404)

    def test_seat_figures_appear_once_the_seats_app_provides_them(self):
        library = published("Live One", *PRAYAGRAJ)
        counts = {library.pk: {"total": 10, "empty": 6, "reserved": 1, "occupied": 3}}
        with mock.patch("apps.libraries.selectors.seat_counts_by_library", return_value=counts):
            item = self.list()["items"][0]
            detail = self.client.get(self.api(f"libraries/{library.pk}/")).json()["data"]
        self.assertEqual(item["seat_counts"]["empty"], 6)
        self.assertEqual(detail["seat_counts"]["total"], 10)
