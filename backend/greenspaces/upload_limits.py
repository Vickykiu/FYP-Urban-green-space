"""Bound CSV uploads before Django spools the complete file to disk."""
from django.core.files.uploadhandler import FileUploadHandler, StopUpload

from .csv_schema import MAX_BYTES


class CsvSizeLimitUploadHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0
        self.active = request is not None and request.path == "/api/admin/datasets/"

    def receive_data_chunk(self, raw_data, start):
        if self.active:
            self.received += len(raw_data)
            if self.received > MAX_BYTES:
                self.request.csv_upload_too_large = True
                raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None
