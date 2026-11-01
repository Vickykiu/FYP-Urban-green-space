"""Initial mapping of the seven entities in proposal Figure 4.16.

Coordinate reference system: WGS84 (SRID 4326). Its coordinates are degrees;
later distance operations must use geography or a suitable metre-based CRS.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator


def validate_geometry(value, allowed_types):
    if value is None:
        return  # Required-field validation handles absence.
    if value.empty or not value.valid:
        raise ValidationError("Provide a valid, non-empty geometry.")
    if value.geom_type not in allowed_types:
        raise ValidationError("Unsupported geometry type for this record.")
    xmin, ymin, xmax, ymax = value.extent
    if not (-180 <= xmin <= xmax <= 180 and -90 <= ymin <= ymax <= 90):
        raise ValidationError("Use WGS84 longitude/latitude coordinates (SRID 4326).")


class AdministrativeArea(models.Model):
    area_id = models.AutoField(primary_key=True)
    area_name = models.CharField(max_length=100)
    area_type = models.CharField(max_length=50, blank=True)
    geometry = models.GeometryField(srid=4326, spatial_index=True)

    class Meta:
        db_table = "administrative_area"
        ordering = ["area_name", "area_id"]

    def clean(self):
        super().clean()
        try:
            validate_geometry(self.geometry, {"Polygon", "MultiPolygon"})
        except ValidationError as error:
            raise ValidationError({"geometry": error.messages}) from error

    def __str__(self):
        return self.area_name


class GreenSpaceCategory(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "green_space_category"
        ordering = ["category_name", "category_id"]
        verbose_name_plural = "green space categories"

    def __str__(self):
        return self.category_name


class DatasetUpload(models.Model):
    dataset_id = models.AutoField(primary_key=True)
    administrator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="admin_id",
    )
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="uploaded")
    total_records = models.PositiveIntegerField(default=0)
    valid_records = models.PositiveIntegerField(default=0)
    invalid_records = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "dataset_upload"
        ordering = ["-uploaded_at", "-dataset_id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_records__gte=models.F("valid_records") + models.F("invalid_records")),
                name="upload_counts_within_total",
            ),
        ]

    def __str__(self):
        return self.file_name


class ValidationResult(models.Model):
    validation_id = models.AutoField(primary_key=True)
    dataset = models.ForeignKey(DatasetUpload, on_delete=models.CASCADE, db_column="dataset_id")
    row_number = models.PositiveIntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    severity = models.CharField(max_length=20, blank=True)
    validation_status = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "validation_result"
        ordering = ["row_number", "validation_id"]


class GreenSpace(models.Model):
    green_space_id = models.AutoField(primary_key=True)
    area = models.ForeignKey(AdministrativeArea, on_delete=models.PROTECT, db_column="area_id")
    category = models.ForeignKey(GreenSpaceCategory, on_delete=models.PROTECT, db_column="category_id")
    dataset = models.ForeignKey(
        DatasetUpload, on_delete=models.SET_NULL, db_column="dataset_id", null=True, blank=True,
    )
    name = models.CharField(max_length=150)
    area_size = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Area in hectares, matching the supplied Figma green-space record form.",
    )
    facilities = models.TextField(blank=True)
    description = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    geometry = models.GeometryField(srid=4326, spatial_index=True)

    class Meta:
        db_table = "green_space"
        ordering = ["name", "green_space_id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(area_size__gte=0) | models.Q(area_size__isnull=True), name="green_space_area_nonnegative"),
            models.CheckConstraint(condition=models.Q(latitude__range=(-90, 90)) | models.Q(latitude__isnull=True), name="green_space_latitude_range"),
            models.CheckConstraint(condition=models.Q(longitude__range=(-180, 180)) | models.Q(longitude__isnull=True), name="green_space_longitude_range"),
            models.CheckConstraint(
                condition=(models.Q(latitude__isnull=True, longitude__isnull=True) | models.Q(latitude__isnull=False, longitude__isnull=False)),
                name="green_space_coordinate_pair",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        try:
            validate_geometry(self.geometry, {"Point", "Polygon", "MultiPolygon"})
        except ValidationError as error:
            errors["geometry"] = error.messages
        if (self.latitude is None) != (self.longitude is None):
            errors["latitude"] = "Provide both latitude and longitude, or leave both empty."
        if self.geometry is not None and "geometry" not in errors and self.geometry.geom_type == "Point":
            lat = Decimal(str(self.geometry.y)).quantize(Decimal("0.000001"))
            lon = Decimal(str(self.geometry.x)).quantize(Decimal("0.000001"))
            if self.latitude is None and self.longitude is None:
                self.latitude, self.longitude = lat, lon
            elif self.latitude != lat or self.longitude != lon:
                errors["geometry"] = "Point geometry must agree with latitude and longitude."
        if errors:
            # Manual-entry forms deliberately exclude raw geometry. Surface
            # geometry errors as form-wide errors, not an excluded field error.
            if "geometry" in errors:
                errors["__all__"] = errors.pop("geometry")
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class PlanningReport(models.Model):
    report_id = models.AutoField(primary_key=True)
    administrator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column="admin_id",
    )
    area = models.ForeignKey(
        AdministrativeArea, on_delete=models.PROTECT, db_column="area_id", null=True, blank=True,
    )
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=100, blank=True)
    reporting_period = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, default="draft")
    generated_at = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=255, blank=True)
    # Implementation support for FR7/FR11: private draft configuration,
    # immutable generated data, and retry-safe creation. No new ERD entity.
    configuration = models.JSONField(default=dict, blank=True, editable=False)
    snapshot = models.JSONField(null=True, blank=True, editable=False)
    request_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        db_table = "planning_report"
        ordering = ["-report_id"]

    def __str__(self):
        return self.title
