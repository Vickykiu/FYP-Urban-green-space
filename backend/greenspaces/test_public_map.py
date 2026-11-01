from unittest.mock import patch

from django.contrib.gis.geos import Point, Polygon
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class PublicMapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = AdministrativeArea.objects.create(area_name="TEST district", area_type="test",
            geometry=Polygon(((101, 2), (102, 2), (102, 4), (101, 4), (101, 2)), srid=4326))
        cls.category = GreenSpaceCategory.objects.create(category_name="TEST category")
        cls.point = GreenSpace.objects.create(name="TEST Alpha", area=cls.area, category=cls.category,
            geometry=Point(101.6, 3.1, srid=4326), latitude="3.100000", longitude="101.600000",
            area_size="1.2500", facilities="TEST facilities", description="TEST description")
        cls.polygon = GreenSpace.objects.create(name="TEST Beta", area=cls.area, category=cls.category,
            geometry=Polygon(((101.7, 3.1), (101.8, 3.1), (101.8, 3.2), (101.7, 3.2), (101.7, 3.1)), srid=4326))

    def test_anonymous_can_view_geojson(self):
        response = self.client.get(reverse("public-green-spaces"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual((data["type"], data["count"]), ("FeatureCollection", 2))
        self.assertEqual(data["features"][0]["geometry"]["coordinates"], [101.6, 3.1])

    def test_bbox_filters_by_spatial_intersection(self):
        data = self.client.get(reverse("public-green-spaces"), {"bbox": "101.59,3.09,101.61,3.11"}).json()
        self.assertEqual([feature["id"] for feature in data["features"]], [self.point.pk])
        data = self.client.get(reverse("public-green-spaces"), {"bbox": "101.75,3.15,101.85,3.25"}).json()
        self.assertEqual([feature["id"] for feature in data["features"]], [self.polygon.pk])

    def test_name_and_category_filters(self):
        response = self.client.get(reverse("public-green-spaces"), {"q": "alpha", "category": self.category.pk})
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(self.client.get(reverse("public-green-spaces"), {"category": 2147483647}).json()["count"], 0)

    def test_detail_contains_only_public_fields(self):
        response = self.client.get(reverse("public-green-space-detail", args=[self.point.pk]))
        data = response.json()
        self.assertEqual(set(data), {"type", "id", "geometry", "properties"})
        self.assertEqual(set(data["properties"]), {"name", "area_id", "area_name", "category_id", "category_name",
            "area_size", "facilities", "description", "latitude", "longitude"})
        self.assertEqual(data["properties"]["area_size"], "1.2500")

    def test_polygon_geometry_is_preserved(self):
        response = self.client.get(reverse("public-green-space-detail", args=[self.polygon.pk]))
        self.assertEqual(response.json()["geometry"]["type"], "Polygon")

    def test_missing_record_returns_404(self):
        self.assertEqual(self.client.get(reverse("public-green-space-detail", args=[2147483647])).status_code, 404)

    def test_boundaries_and_real_counts(self):
        data = self.client.get(reverse("public-administrative-areas"), {"bbox": "101.5,3,101.9,3.3"}).json()
        self.assertEqual(data["count"], 1)
        options = self.client.get(reverse("public-map-options")).json()
        self.assertEqual(options["green_space_count"], 2)
        self.assertEqual(options["categories"][0]["green_space_count"], 2)

    def test_pagination_is_explicit(self):
        with patch("greenspaces.public_views.PAGE_SIZE", 1):
            first = self.client.get(reverse("public-green-spaces")).json()
            second = self.client.get(reverse("public-green-spaces"), {"page": 2}).json()
            self.assertTrue(first["has_next"])
            self.assertFalse(second["has_next"])
            self.assertNotEqual(first["features"][0]["id"], second["features"][0]["id"])

    def test_invalid_query_returns_400(self):
        for params in ({"bbox": "nan,2,3,4"}, {"page": "-1"}, {"q": "x" * 151}):
            self.assertEqual(self.client.get(reverse("public-green-spaces"), params).status_code, 400)

    def test_public_routes_reject_writes(self):
        for url in (reverse("public-green-spaces"), reverse("public-green-space-detail", args=[self.point.pk]),
                    reverse("public-administrative-areas"), reverse("public-map-options")):
            for method in (self.client.post, self.client.put, self.client.delete):
                self.assertEqual(method(url).status_code, 405)
        self.assertEqual(GreenSpace.objects.count(), 2)

    def test_unavailable_database_is_not_reported_as_empty(self):
        with patch("greenspaces.public_views.GreenSpace.objects.select_related", side_effect=DatabaseError("test only")):
            response = self.client.get(reverse("public-green-spaces"))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("test only", response.content.decode())

    def test_no_matching_records_is_successfully_empty(self):
        data = self.client.get(reverse("public-green-spaces"), {"q": "does not exist"}).json()
        self.assertEqual((data["count"], data["features"], data["has_next"]), (0, [], False))
