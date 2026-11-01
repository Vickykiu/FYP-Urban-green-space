"""Private staging: paths use server-assigned IDs, never uploaded filenames."""
from pathlib import Path

from django.conf import settings

from .csv_schema import MAX_BYTES, CsvFileError, decode_csv


def source_path(dataset_id):
    if type(dataset_id) is not int or dataset_id <= 0:
        raise ValueError("A positive server-assigned dataset ID is required.")
    root = (Path(settings.MEDIA_ROOT) / "private_uploads").resolve()
    path = (root / f"{dataset_id}.csv").resolve()
    if path.parent != root:
        raise ValueError("Invalid staging path.")
    return path


def write_source(dataset_id, raw):
    path = source_path(dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation never overwrites a file left by an earlier upload.
    with path.open("xb") as target:
        try:
            target.write(raw)
        except BaseException:
            target.close()
            path.unlink(missing_ok=True)
            raise
    return path


def read_source(dataset_id):
    with source_path(dataset_id).open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    decode_csv(raw)
    return raw


def read_upload(upload):
    if not upload.name.lower().endswith(".csv"):
        raise CsvFileError("Only .csv files are accepted.")
    if upload.size > MAX_BYTES:
        raise CsvFileError("The CSV must be no larger than 5 MiB.")
    raw = bytearray()
    for chunk in upload.chunks():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES:
            raise CsvFileError("The CSV must be no larger than 5 MiB.")
    decode_csv(raw)
    return bytes(raw)
