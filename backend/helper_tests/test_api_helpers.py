"""No-database tests for JSON parsing and access guards, not PostGIS integration."""
import json
import unittest
from types import SimpleNamespace

from django.conf import settings

if not settings.configured:
    settings.configure(SECRET_KEY="unit-tests-only", DEFAULT_CHARSET="utf-8", USE_I18N=False,
                       ALLOWED_HOSTS=["testserver"], DATA_UPLOAD_MAX_MEMORY_SIZE=2621440)

from django.http import JsonResponse
from django.test import RequestFactory
from config.api import read_record_json, staff_permission


class ApiHelperTests(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def parse(self, payload):
        request = self.factory.post("/api/admin/green-spaces/", payload, content_type="application/json")
        return read_record_json(request, ("name", "area", "category", "latitude", "longitude", "area_size"))

    def test_rejects_invalid_json_and_non_objects(self):
        for body in ("{", "null", "[]", '"text"', '{"latitude":NaN}', '{"latitude":1e9999}'):
            with self.subTest(body=body):
                payload, response = self.parse(body)
                self.assertIsNone(payload)
                self.assertEqual(response.status_code, 400)

    def test_rejects_mass_assignment(self):
        for field in ("is_staff", "dataset", "geometry", "green_space_id"):
            payload, response = self.parse({field: 1})
            self.assertIsNone(payload)
            self.assertEqual(response.status_code, 400)

    def test_rejects_fractional_and_boolean_ids(self):
        for value in (1.5, 1.0, True, False, -1, 0, "1.5", None, [], {}, 2147483648):
            with self.subTest(value=value):
                self.assertEqual(self.parse({"area": value})[1].status_code, 400)

    def test_accepts_supported_scalar_fields(self):
        source = {"name": "Test", "area": 1, "category": "2", "latitude": "3.100000", "longitude": "101.600000", "area_size": None}
        payload, response = self.parse(source)
        self.assertIsNone(response)
        self.assertEqual(payload, source)

    def test_content_type_is_required(self):
        request = self.factory.post("/api/admin/green-spaces/", {"name": "test"})
        self.assertEqual(read_record_json(request, ("name",))[1].status_code, 415)

    def test_rejects_wrong_field_types(self):
        for payload in ({"name": 123}, {"latitude": {}}, {"longitude": True}):
            self.assertEqual(self.parse(payload)[1].status_code, 400)

    def test_staff_permission_guard(self):
        calls = []
        @staff_permission("greenspaces.add_greenspace")
        def protected(request):
            calls.append(True)
            return JsonResponse({"ok": True})
        for authenticated, active, staff, permission, expected in (
            (False, True, True, True, 401), (True, False, True, True, 403),
            (True, True, False, True, 403), (True, True, True, False, 403),
            (True, True, True, True, 200),
        ):
            user = SimpleNamespace(is_authenticated=authenticated, is_active=active, is_staff=staff,
                                   has_perm=lambda name, allowed=permission: allowed)
            response = protected(SimpleNamespace(user=user))
            self.assertEqual(response.status_code, expected)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
