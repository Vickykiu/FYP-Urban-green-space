"""Integration tests: require native GIS libraries and a separate PostGIS test database."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Polygon
from django.test import Client, TestCase
from django.urls import reverse

from .forms import GreenSpaceForm
from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory


class AdministratorRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Synthetic geometry for isolated tests; not an official district boundary.
        cls.area = AdministrativeArea.objects.create(
            area_name="TEST area only", area_type="test",
            geometry=Polygon(((100, 2), (102, 2), (102, 4), (100, 4), (100, 2)), srid=4326),
        )
        cls.category = GreenSpaceCategory.objects.create(category_name="TEST category only")
        cls.admin = get_user_model().objects.create_superuser(
            username="test_admin", email="admin@example.test", password="Test-only-Password-492!",
        )
        cls.staff = get_user_model().objects.create_user(
            username="limited_staff", email="staff@example.test",
            password="Test-only-Password-492!", is_staff=True,
        )

    def payload(self, **changes):
        values = {
            "name": "TEST green space only", "area": self.area.pk, "category": self.category.pk,
            "area_size": "1.2500", "facilities": "Test fixture", "description": "Not real data",
            "latitude": "3.100000", "longitude": "101.600000",
        }
        values.update(changes)
        return values

    def create_record(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin-records"), self.payload(), content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["green_space_id"]

    def test_anonymous_cannot_read_records(self):
        self.assertEqual(self.client.get(reverse("admin-records")).status_code, 401)

    def test_staff_without_permission_cannot_write(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("admin-records"), self.payload(), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_permission_does_not_grant_non_staff_access(self):
        self.staff.is_staff = False
        self.staff.save(update_fields=["is_staff"])
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label="greenspaces", codename="view_greenspace"))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin-records")).status_code, 403)

    def test_create_uses_longitude_latitude_order(self):
        record = GreenSpace.objects.get(pk=self.create_record())
        self.assertEqual(record.geometry.srid, 4326)
        self.assertAlmostEqual(record.geometry.x, 101.6)
        self.assertAlmostEqual(record.geometry.y, 3.1)
        self.assertIsNone(record.dataset_id)

    def test_invalid_input_does_not_insert_rows(self):
        self.client.force_login(self.admin)
        for changes in ({"latitude": "91"}, {"longitude": "181"}, {"latitude": "NaN"},
                        {"name": "   "}, {"area_size": "-1"}, {"category": 999999},
                        {"geometry": {"type": "Point", "coordinates": [0, 0]}}, {"dataset": 123}):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("admin-records"), self.payload(**changes), content_type="application/json")
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_update_rebuilds_point_and_delete_removes_record(self):
        pk = self.create_record()
        detail_url = reverse("admin-record-detail", args=[pk])
        response = self.client.put(detail_url, self.payload(name="TEST updated", longitude="101.650000"), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertAlmostEqual(GreenSpace.objects.get(pk=pk).geometry.x, 101.65)
        self.assertEqual(self.client.delete(detail_url).status_code, 200)
        self.assertFalse(GreenSpace.objects.filter(pk=pk).exists())
        self.assertEqual(self.client.get(detail_url).status_code, 404)

    def test_invalid_update_leaves_existing_record_unchanged(self):
        pk = self.create_record()
        url = reverse("admin-record-detail", args=[pk])
        for changes in ({"name": "Changed", "latitude": "999"},
                        {"name": " ", "longitude": "101.650000"},
                        {"latitude": "invalid", "longitude": "101.650000"},
                        {"latitude": None, "longitude": None}):
            with self.subTest(changes=changes):
                response = self.client.put(url, self.payload(**changes), content_type="application/json")
                self.assertEqual(response.status_code, 400, response.content)
                record = GreenSpace.objects.get(pk=pk)
                self.assertEqual(record.name, "TEST green space only")
                self.assertAlmostEqual(record.geometry.x, 101.6)

    def test_put_requires_all_editable_fields(self):
        pk = self.create_record()
        response = self.client.put(reverse("admin-record-detail", args=[pk]),
                                   {"name": "Incomplete edit"}, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_permissions_are_checked_for_each_action(self):
        pk = self.create_record()
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="greenspaces", codename="view_greenspace"))
        self.client.force_login(self.staff)
        detail_url = reverse("admin-record-detail", args=[pk])
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(self.client.put(detail_url, self.payload(), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(detail_url).status_code, 403)
        self.assertTrue(GreenSpace.objects.filter(pk=pk).exists())

    def test_edit_preserves_existing_polygon(self):
        boundary = Polygon(((101.5, 3), (101.7, 3), (101.7, 3.2), (101.5, 3.2), (101.5, 3)), srid=4326)
        record = GreenSpace.objects.create(name="TEST polygon", area=self.area, category=self.category, geometry=boundary)
        form = GreenSpaceForm(self.payload(latitude=None, longitude=None), instance=record)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        record.refresh_from_db()
        self.assertTrue(record.geometry.equals_exact(boundary, 0))

    def test_crud_rejects_missing_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse("admin-records"), self.payload(), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        token = client.get(reverse("admin-session")).json()["csrf_token"]
        response = client.post(reverse("admin-records"), self.payload(), content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201, response.content)

    def test_admin_login_and_logout(self):
        response = self.client.post(reverse("admin:login"), {
            "username": "test_admin", "password": "Test-only-Password-492!", "next": "/admin/",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("admin-records")).status_code, 200)
        self.client.post(reverse("admin:logout"))
        self.assertEqual(self.client.get(reverse("admin-records")).status_code, 401)

    def test_list_is_paginated_and_lookup_values_are_available(self):
        self.create_record()
        result = self.client.get(reverse("admin-records")).json()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["page_size"], 50)
        self.assertEqual(self.client.get(reverse("admin-records"), {"page": "bad"}).status_code, 400)
        result = self.client.get(reverse("admin-lookups")).json()
        self.assertEqual(result["areas"][0]["area_id"], self.area.pk)

    def test_admin_form_uses_the_same_coordinate_validation(self):
        self.client.force_login(self.admin)
        url = reverse("admin:greenspaces_greenspace_add")
        response = self.client.post(url, self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GreenSpace.objects.count(), 1)
