"""Version-one CSV contract. Pure Python so it can be tested without PostGIS."""
import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
COLUMNS = ("name", "area_id", "category_id", "area_size", "facilities",
           "description", "latitude", "longitude", "geometry_wkt")
REQUIRED_COLUMNS = {"name", "area_id", "category_id"}


class CsvFileError(ValueError):
    """The file cannot be safely interpreted as the supported CSV format."""


@dataclass
class Issue:
    row_number: int | None
    field_name: str
    error_message: str


@dataclass
class CsvRow:
    row_number: int
    values: dict


@dataclass
class CsvBatch:
    total_records: int
    rows: list[CsvRow]
    issues: list[Issue]


def decode_csv(raw):
    if not raw:
        raise CsvFileError("The uploaded file is empty.")
    if len(raw) > MAX_BYTES:
        raise CsvFileError("The CSV must be no larger than 5 MiB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvFileError("Save the CSV as UTF-8, then upload it again.") from exc
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text):
        raise CsvFileError("Binary data or unsupported control characters were found.")
    return text


def _identifier(text):
    if not (text.isascii() and text.isdecimal() and len(text) <= 10 and 0 < int(text) <= 2147483647):
        raise ValueError("Use an existing positive integer ID.")
    return int(text)


def _decimal(text, places, digits, minimum, maximum=None):
    if not text:
        return None
    if not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", text):
        raise ValueError("Use a finite decimal number without units or scientific notation.")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Use a finite decimal number.") from exc
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"Value must be between {minimum} and {maximum}." if maximum is not None
                         else f"Value must be at least {minimum}.")
    decimals = max(-value.as_tuple().exponent, 0)
    whole = max(value.adjusted() + 1, 0)
    if decimals > places or whole > digits - places:
        raise ValueError(f"Use at most {digits - places} integer digits and {places} decimal places.")
    return value


def parse_csv(raw):
    reader = csv.reader(io.StringIO(decode_csv(raw), newline=""), strict=True)
    try:
        header = next(reader, None)
        if not header:
            raise CsvFileError("The CSV needs a header row.")
        header = [value.strip() for value in header]
        if len(header) != len(set(header)):
            raise CsvFileError("Duplicate column headers are not allowed.")
        if set(header) - set(COLUMNS):
            raise CsvFileError("Unknown column header. Use the downloaded CSV template.")
        if REQUIRED_COLUMNS - set(header):
            raise CsvFileError("Required headers: name, area_id, category_id.")
        if "geometry_wkt" not in header and not {"latitude", "longitude"} <= set(header):
            raise CsvFileError("Include latitude and longitude columns, or geometry_wkt.")
        source_rows = []
        for row_number, values in enumerate(reader, start=2):
            if not values or not any(value.strip() for value in values):
                continue
            if len(values) != len(header):
                raise CsvFileError(f"CSV record {row_number} has a different number of fields than the header.")
            source_rows.append((row_number, dict(zip(header, values))))
            if len(source_rows) > MAX_ROWS:
                raise CsvFileError("Use at most 1,000 data records per file; split larger datasets.")
    except csv.Error as exc:
        raise CsvFileError("Malformed CSV. Check quotation marks, field lengths, and commas.") from exc
    if not source_rows:
        raise CsvFileError("The CSV contains a header but no data records.")

    rows, issues = [], []
    for row_number, source in source_rows:
        values = {column: source.get(column, "").strip() for column in COLUMNS}
        row_issues = []

        def problem(field, message):
            row_issues.append(Issue(row_number, field, message))

        if not values["name"] or len(values["name"]) > 150:
            problem("name", "Name is required and must be no longer than 150 characters.")
        for field in ("facilities", "description"):
            if len(values[field]) > 20000:
                problem(field, "Use at most 20,000 characters.")
        if len(values["geometry_wkt"]) > 100000:
            problem("geometry_wkt", "Use at most 100,000 characters per geometry.")
        for field in ("area_id", "category_id"):
            try:
                values[field] = _identifier(values[field])
            except ValueError as exc:
                problem(field, str(exc))
        for field, places, digits, low, high in (
            ("area_size", 4, 14, 0, None), ("latitude", 6, 9, -90, 90),
            ("longitude", 6, 9, -180, 180),
        ):
            try:
                values[field] = _decimal(values[field], places, digits, low, high)
            except ValueError as exc:
                problem(field, str(exc))
        if not any(issue.field_name in {"latitude", "longitude"} for issue in row_issues):
            lat, lon = values["latitude"], values["longitude"]
            if (lat is None) != (lon is None):
                problem("latitude", "Provide both latitude and longitude, or leave both blank with WKT geometry.")
            elif lat is None and not values["geometry_wkt"]:
                problem("geometry_wkt", "Provide latitude/longitude or a WGS84 WKT geometry.")
        if values["geometry_wkt"] and not re.match(
            r"^(POINT|POLYGON|MULTIPOLYGON)\s*\(", values["geometry_wkt"], re.IGNORECASE,
        ):
            problem("geometry_wkt", "Use plain 2D POINT, POLYGON, or MULTIPOLYGON WKT in WGS84; no SRID prefix.")
        issues.extend(row_issues)
        if not row_issues:
            rows.append(CsvRow(row_number, values))
    return CsvBatch(len(source_rows), rows, issues)
