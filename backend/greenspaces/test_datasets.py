"""PostGIS integration tests; all uploads and accounts are disposable fixtures."""
import csv
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .csv_schema import COLUMNS
from .dataset_storage import source_path
from .models import AdministrativeArea, DatasetUpload, GreenSpace, GreenSpaceCategory, ValidationResult


class DatasetImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="csv_test_admin", email="csv@example.test", password="Test-only-Password-492!",
        )
        cls.editor = get_user_model().objects.create_user(username="csv_editor", is_staff=True)
        cls.other_editor = get_user_model().objects.create_user(username="other_csv_editor", is_staff=True)
        permissions = Permission.objects.filter(content_type__app_label="greenspaces", codename__in=[
            "view_datasetupload", "add_datasetupload", "change_datasetupload", "view_greenspace", "add_greenspace",
        ])
        cls.editor.user_permissions.set(permissions)
        cls.other_editor.user_permissions.set(permissions)
        cls.area = AdministrativeArea.objects.create(
            area_name="TEST area only", area_type="test",
            geometry=Polygon(((100, 2), (102, 2), (102, 4), (100, 4), (100, 2)), srid=4326),
        )
        cls.category = GreenSpaceCategory.objects.create(category_name="TEST category only")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="petaling-dataset-integration-")
        self.addCleanup(temporary.cleanup)
        override = override_settings(MEDIA_ROOT=temporary.name)
        override.enable()
        self.addCleanup(override.disable)
        self.client.force_login(self.admin)

    def row(self, **changes):
        return {"name": "TEST green space - synthetic", "area_id": self.area.pk,
                "category_id": self.category.pk, "area_size": "1.2500",
                "latitude": "3.100000", "longitude": "101.600000", **changes}

    def content(self, rows):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([row.get(column, "") for column in COLUMNS])
        return output.getvalue().encode("utf-8")

    def upload(self, rows=None):
        raw = self.content(rows if rows is not None else [self.row()])
        response = self.client.post(reverse("datasets"), {"file": SimpleUploadedFile("test.csv", raw)})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["dataset_id"]

    def validate(self, dataset_id):
        response = self.client.post(reverse("dataset-validate", args=[dataset_id]))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def confirm(self, dataset_id, token):
        return self.client.post(reverse("dataset-import", args=[dataset_id]),
                                {"validation_token": token}, content_type="application/json")

    def test_upload_does_not_import_until_validated_and_confirmed(self):
        pk = self.upload()
        self.assertEqual(DatasetUpload.objects.get(pk=pk).status, "uploaded")
        self.assertEqual(GreenSpace.objects.count(), 0)
        result = self.validate(pk)
        self.assertTrue(result["ready_to_import"])
        self.assertEqual(GreenSpace.objects.count(), 0)
        response = self.confirm(pk, result["validation_token"])
        self.assertEqual(response.status_code, 200, response.content)
        record = GreenSpace.objects.get(dataset_id=pk)
        self.assertEqual(record.geometry.srid, 4326)
        self.assertAlmostEqual(record.geometry.x, 101.6)
        self.assertAlmostEqual(record.geometry.y, 3.1)
        self.assertEqual(DatasetUpload.objects.get(pk=pk).status, "imported")

    def test_one_invalid_row_blocks_the_entire_file(self):
        pk = self.upload([self.row(), self.row(name="TEST invalid", latitude="91")])
        result = self.validate(pk)
        self.assertEqual((result["total_records"], result["valid_records"], result["invalid_records"]), (2, 1, 1))
        self.assertFalse(result["ready_to_import"])
        self.assertIsNone(result["validation_token"])
        self.assertEqual(result["issues"][0]["row_number"], 3)
        self.assertNotEqual(self.confirm(pk, "not-a-token").status_code, 200)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_unknown_reference_and_duplicate_rows_are_reported(self):
        pk = self.upload([self.row(), self.row(), self.row(name="TEST unknown", category_id=2147483647)])
        result = self.validate(pk)
        self.assertEqual(result["valid_records"], 1)
        self.assertEqual(result["invalid_records"], 2)
        self.assertEqual({issue["field_name"] for issue in result["issues"]}, {"name", "category_id"})

    def test_polygon_wkt_is_preserved(self):
        wkt = "POLYGON ((101.5 3, 101.7 3, 101.7 3.2, 101.5 3.2, 101.5 3))"
        pk = self.upload([self.row(latitude="", longitude="", geometry_wkt=wkt)])
        result = self.validate(pk)
        self.assertTrue(result["ready_to_import"], result)
        self.assertEqual(self.confirm(pk, result["validation_token"]).status_code, 200)
        record = GreenSpace.objects.get(dataset_id=pk)
        self.assertEqual(record.geometry.geom_type, "Polygon")
        self.assertIsNone(record.latitude)

    def test_invalid_geometry_and_point_coordinate_mismatch(self):
        rows = [self.row(geometry_wkt="POINT (101.7 3.1)"),
                self.row(name="TEST malformed", geometry_wkt="POLYGON ((bad))"),
                self.row(name="TEST crossing", latitude="", longitude="",
                         geometry_wkt="POLYGON ((101 3, 102 4, 102 3, 101 4, 101 3))")]
        result = self.validate(self.upload(rows))
        self.assertEqual(result["invalid_records"], 3)
        self.assertFalse(result["ready_to_import"])

    def test_repeat_confirmation_never_duplicates_the_same_dataset(self):
        pk = self.upload()
        token = self.validate(pk)["validation_token"]
        self.assertEqual(self.confirm(pk, token).status_code, 200)
        response = self.confirm(pk, token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["already_imported"])
        self.assertEqual(GreenSpace.objects.filter(dataset_id=pk).count(), 1)
        self.assertEqual(self.client.post(reverse("dataset-validate", args=[pk])).status_code, 409)

    def test_staged_file_changes_invalidate_confirmation(self):
        pk = self.upload()
        token = self.validate(pk)["validation_token"]
        source_path(pk).write_bytes(self.content([self.row(name="TEST changed after validation")]))
        self.assertEqual(self.confirm(pk, token).status_code, 409)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_token_is_bound_to_dataset(self):
        first, second = self.upload(), self.upload()
        token = self.validate(first)["validation_token"]
        self.validate(second)
        self.assertEqual(self.confirm(second, token).status_code, 409)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_removed_reference_is_rechecked_at_import(self):
        pk = self.upload()
        token = self.validate(pk)["validation_token"]
        GreenSpaceCategory.objects.filter(pk=self.category.pk).delete()
        response = self.confirm(pk, token)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(DatasetUpload.objects.get(pk=pk).status, "invalid")
        self.assertTrue(ValidationResult.objects.filter(dataset_id=pk, field_name="category_id").exists())
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_insertion_failure_rolls_back_every_insert(self):
        pk = self.upload([self.row(), self.row(name="TEST second")])
        token = self.validate(pk)["validation_token"]

        def fail_after_first(records, **kwargs):
            records[0].save()
            raise IntegrityError("Deliberate integration-test failure")

        with patch("greenspaces.datasets.GreenSpace.objects.bulk_create", side_effect=fail_after_first):
            response = self.confirm(pk, token)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(GreenSpace.objects.count(), 0)
        self.assertEqual(DatasetUpload.objects.get(pk=pk).status, "validated")

    def test_editor_cannot_read_validate_or_import_another_editors_upload(self):
        self.client.force_login(self.editor)
        pk = self.upload()
        token = self.validate(pk)["validation_token"]
        self.client.force_login(self.other_editor)
        self.assertEqual(self.client.get(reverse("dataset-detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dataset-validate", args=[pk])).status_code, 404)
        self.assertEqual(self.confirm(pk, token).status_code, 404)
        self.assertEqual(self.client.get(reverse("datasets")).json()["count"], 0)

    def test_import_requires_add_green_space_permission(self):
        self.client.force_login(self.editor)
        pk = self.upload()
        token = self.validate(pk)["validation_token"]
        self.editor.user_permissions.remove(Permission.objects.get(content_type__app_label="greenspaces", codename="add_greenspace"))
        self.assertEqual(self.confirm(pk, token).status_code, 403)
        self.assertEqual(GreenSpace.objects.count(), 0)

    def test_missing_upload_permission_and_anonymous_access(self):
        self.editor.user_permissions.clear()
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse("datasets")).status_code, 403)
        response = self.client.post(reverse("datasets"), {"file": SimpleUploadedFile("test.csv", self.content([self.row()]))})
        self.assertEqual(response.status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("datasets")).status_code, 401)

    def test_csrf_is_required_for_upload_validation_and_import(self):
        pk = self.upload()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in (reverse("datasets"), reverse("dataset-validate", args=[pk]), reverse("dataset-import", args=[pk])):
            self.assertEqual(client.post(url).status_code, 403)

    def test_invalid_file_and_failed_storage_do_not_create_metadata(self):
        response = self.client.post(reverse("datasets"), {"file": SimpleUploadedFile("bad.xlsx", b"text")})
        self.assertEqual(response.status_code, 400)
        with patch("greenspaces.datasets.write_source", side_effect=OSError("test only")):
            response = self.client.post(reverse("datasets"), {"file": SimpleUploadedFile("good.csv", self.content([self.row()]))})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(DatasetUpload.objects.count(), 0)

    def test_history_template_and_repeat_validation(self):
        pk = self.upload([self.row(latitude="91")])
        first = self.validate(pk)
        second = self.validate(pk)
        self.assertEqual(first["issue_count"], second["issue_count"])
        self.assertEqual(self.client.get(reverse("datasets")).json()["count"], 1)
        self.assertEqual(self.client.get(reverse("dataset-detail", args=[pk]), {"page": 2}).json()["issues"], [])
        self.assertEqual(self.client.get(reverse("datasets"), {"page": "bad"}).status_code, 400)
        template = self.client.get(reverse("dataset-template"))
        self.assertEqual(template.status_code, 200)
        self.assertEqual(template.content.decode().strip(), ",".join(COLUMNS))

    def test_structure_errors_have_no_misleading_row_totals(self):
        response = self.client.post(reverse("datasets"), {"file": SimpleUploadedFile("header-only.csv", self.content([]))})
        self.assertEqual(response.status_code, 201)
        result = self.validate(response.json()["dataset_id"])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["total_records"], 0)
        self.assertEqual(result["issues"][0]["field_name"], "_file")
