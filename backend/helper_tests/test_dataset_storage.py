import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings

if not settings.configured:
    settings.configure(SECRET_KEY="unit-tests-only", DEFAULT_CHARSET="utf-8", USE_I18N=False,
                       ALLOWED_HOSTS=["testserver"], DATA_UPLOAD_MAX_MEMORY_SIZE=2621440)

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadhandler import StopUpload
from django.test import RequestFactory, override_settings

from greenspaces.csv_schema import CsvFileError
from greenspaces.dataset_storage import read_source, read_upload, source_path, write_source
from greenspaces.upload_limits import CsvSizeLimitUploadHandler


class DatasetStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="petaling-csv-tests-")
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_ROOT=self.temp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_source_roundtrip_is_private_and_id_based(self):
        raw = b"name,area_id,category_id,latitude,longitude\nTEST,1,1,3,101\n"
        path = write_source(1, raw)
        self.assertEqual(path, Path(self.temp.name).resolve() / "private_uploads" / "1.csv")
        self.assertEqual(read_source(1), raw)

    def test_existing_source_is_never_overwritten(self):
        write_source(1, b"original")
        with self.assertRaises(FileExistsError):
            write_source(1, b"replacement")
        self.assertEqual(read_source(1), b"original")

    def test_rejects_untrusted_path_components(self):
        for value in ("../file", "C:\\file", 0, -1, True, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_path(value)

    def test_csv_filename_and_encoding_checks(self):
        for name, raw in (("park.xlsx", b"text"), ("park.csv.exe", b"text"), ("park.csv", b"\x00")):
            with self.assertRaises(CsvFileError):
                read_upload(SimpleUploadedFile(name, raw))
        self.assertEqual(read_upload(SimpleUploadedFile("PARK.CSV", b"text")), b"text")

    def test_upload_limit_counts_chunks(self):
        request = SimpleNamespace(path="/api/admin/datasets/")
        handler = CsvSizeLimitUploadHandler(request)
        with patch("greenspaces.upload_limits.MAX_BYTES", 5):
            self.assertEqual(handler.receive_data_chunk(b"123", 0), b"123")
            with self.assertRaises(StopUpload):
                handler.receive_data_chunk(b"456", 3)
        self.assertTrue(request.csv_upload_too_large)

    def test_upload_limit_does_not_change_other_routes(self):
        handler = CsvSizeLimitUploadHandler(SimpleNamespace(path="/another-route/"))
        with patch("greenspaces.upload_limits.MAX_BYTES", 1):
            self.assertEqual(handler.receive_data_chunk(b"123", 0), b"123")

    def test_real_multipart_parsing_honors_upload_limit(self):
        handlers = ["greenspaces.upload_limits.CsvSizeLimitUploadHandler",
                    "django.core.files.uploadhandler.MemoryFileUploadHandler",
                    "django.core.files.uploadhandler.TemporaryFileUploadHandler"]
        with override_settings(FILE_UPLOAD_HANDLERS=handlers), patch("greenspaces.upload_limits.MAX_BYTES", 10):
            request = RequestFactory().post("/api/admin/datasets/", {"file": SimpleUploadedFile("data.csv", b"x" * 11)})
            self.assertEqual(len(request.FILES), 0)
            self.assertTrue(request.csv_upload_too_large)


if __name__ == "__main__":
    unittest.main()
