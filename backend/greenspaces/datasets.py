"""Upload -> validate -> explicitly confirm an all-or-nothing import (FR8/FR9)."""
import hashlib
import ntpath

from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSGeometry, Point
from django.contrib.gis.geos.error import GEOSException
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from .csv_schema import CsvFileError, Issue, parse_csv
from .dataset_storage import read_source, read_upload, write_source
from .models import AdministrativeArea, DatasetUpload, GreenSpace, GreenSpaceCategory, ValidationResult

TOKEN_SALT = "petaling-gis.dataset-confirmation.v1"
TOKEN_MAX_AGE = 24 * 60 * 60


class DatasetProblem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def visible_datasets(user):
    query = DatasetUpload.objects.all()
    return query if user.is_superuser else query.filter(administrator=user)


def locked_dataset(user, dataset_id):
    dataset = visible_datasets(user).select_for_update().filter(pk=dataset_id).first()
    if dataset is None:
        raise DatasetProblem("Dataset not found.", 404)
    return dataset


def create_dataset(user, upload):
    raw = read_upload(upload)
    file_name = ntpath.basename(upload.name)
    if not file_name or len(file_name) > 255:
        raise DatasetProblem("Use a filename no longer than 255 characters.")
    path = None
    try:
        with transaction.atomic():
            dataset = DatasetUpload.objects.create(administrator=user, file_name=file_name)
            path = write_source(dataset.pk, raw)
    except BaseException:
        # Only remove a newly created staging file if its DB creation failed.
        # Never remove a pre-existing file or any user-selected path.
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return dataset


def prepare_records(raw, lock_references=False):
    try:
        batch = parse_csv(raw)
    except CsvFileError as exc:
        return 0, [], [Issue(None, "_file", str(exc))]
    areas = AdministrativeArea.objects.filter(pk__in={row.values["area_id"] for row in batch.rows}).order_by("pk")
    categories = GreenSpaceCategory.objects.filter(pk__in={row.values["category_id"] for row in batch.rows}).order_by("pk")
    if lock_references:
        areas, categories = areas.select_for_update(), categories.select_for_update()
    area_ids = set(areas.values_list("pk", flat=True))
    category_ids = set(categories.values_list("pk", flat=True))
    issues, records, seen = list(batch.issues), [], set()
    for row in batch.rows:
        values, invalid = row.values, False
        for field, known in (("area_id", area_ids), ("category_id", category_ids)):
            if values[field] not in known:
                issues.append(Issue(row.row_number, field, "This reference ID does not exist; choose one from the lookup list."))
                invalid = True
        if invalid:
            continue
        try:
            geometry = (GEOSGeometry(values["geometry_wkt"], srid=4326) if values["geometry_wkt"]
                        else Point(float(values["longitude"]), float(values["latitude"]), srid=4326))
            if geometry.hasz:
                raise ValidationError("Use two-dimensional WGS84 geometry.")
            record = GreenSpace(**{field: values[field] for field in (
                "name", "area_id", "category_id", "area_size", "facilities", "description", "latitude", "longitude",
            )}, geometry=geometry)
            # References were checked in two bounded queries above. The SQL
            # constraints still run during insertion, inside the transaction.
            record.full_clean(exclude={"area", "category", "dataset"},
                              validate_unique=False, validate_constraints=False)
        except (GEOSException, GDALException, ValueError, TypeError):
            issues.append(Issue(row.row_number, "geometry_wkt", "Geometry could not be read. Check the WKT in QGIS."))
            continue
        except ValidationError as exc:
            details = exc.message_dict if hasattr(exc, "message_dict") else {"geometry_wkt": exc.messages}
            for field, messages in details.items():
                issues.append(Issue(row.row_number, "geometry_wkt" if field in {"geometry", "__all__"} else field,
                                    " ".join(messages)))
            continue
        key = (record.name.casefold(), record.area_id, record.category_id, record.geometry.wkt)
        if key in seen:
            issues.append(Issue(row.row_number, "name", "Duplicate name, area, category, and geometry within this file."))
            continue
        seen.add(key)
        records.append(record)
    return batch.total_records, records, issues


def save_validation(dataset, total, records, issues):
    ValidationResult.objects.filter(dataset=dataset).delete()
    ValidationResult.objects.bulk_create([
        ValidationResult(dataset=dataset, row_number=issue.row_number, field_name=issue.field_name,
                         error_message=issue.error_message, severity="error", validation_status="invalid")
        for issue in issues
    ], batch_size=500)
    dataset.total_records = total
    dataset.valid_records = len(records)
    dataset.invalid_records = total - len(records)
    dataset.status = "invalid" if issues else "validated"
    dataset.save(update_fields=["total_records", "valid_records", "invalid_records", "status"])


def validate_dataset(user, dataset_id):
    with transaction.atomic():
        dataset = locked_dataset(user, dataset_id)
        if dataset.status == "imported":
            raise DatasetProblem("This dataset has already been imported and cannot be revalidated.", 409)
        raw = read_source(dataset.pk)
        total, records, issues = prepare_records(raw)
        save_validation(dataset, total, records, issues)
        token = None if issues else signing.dumps(
            {"dataset_id": dataset.pk, "sha256": hashlib.sha256(raw).hexdigest()}, salt=TOKEN_SALT,
        )
    return dataset, token


def import_dataset(user, dataset_id, token):
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise DatasetProblem("Provide the validation_token returned by successful validation.")
    try:
        approved = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature as exc:
        raise DatasetProblem("The confirmation token is invalid or expired. Validate the dataset again.", 409) from exc
    if not isinstance(approved, dict) or approved.get("dataset_id") != dataset_id:
        raise DatasetProblem("The confirmation token belongs to a different dataset.", 409)
    with transaction.atomic():
        dataset = locked_dataset(user, dataset_id)
        # Locking the dataset row serializes duplicate Confirm Import requests.
        if dataset.status == "imported":
            return dataset, True
        if dataset.status != "validated":
            raise DatasetProblem("The dataset must pass validation before import.", 409)
        raw = read_source(dataset.pk)
        if approved.get("sha256") != hashlib.sha256(raw).hexdigest():
            raise DatasetProblem("The staged file changed after validation. Validate it again.", 409)
        # Repeat checks because a referenced area/category may have changed
        # since the administrator viewed the first validation result.
        total, records, issues = prepare_records(raw, lock_references=True)
        save_validation(dataset, total, records, issues)
        if issues:
            return dataset, False
        for record in records:
            record.dataset = dataset
        GreenSpace.objects.bulk_create(records, batch_size=500)
        dataset.status = "imported"
        dataset.save(update_fields=["status"])
    return dataset, False
