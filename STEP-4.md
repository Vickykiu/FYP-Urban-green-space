# Step 4 CSV upload, validation, and confirmed import

This stage prepares the backend for FR8 and FR9 and Use Cases 08/09 in your report. It uses Django/GeoDjango, PostgreSQL/PostGIS, and Python's built-in CSV support. No new application framework or Docker is added.

**Status:** code prepared; 28 database-independent tests passed. Seventeen new upload/import integration tests are written but have not run because native GIS libraries and the database configuration are still incomplete. No real datasets, accounts, or green-space records were created. The original seven database entities are unchanged, so this step adds no schema migration of its own; Step 2's initial migrations are still required.

The frontend remains the temporary setup checker. The upload, validation, Replace File, and Confirm Import screens will follow your Figma reference when the React interface is implemented. For this backend step, use Postman.

## What the workflow does

```text
Upload CSV -> Validate -> Review results -> Confirm Import -> Green-space records
                            |
                            +-- Any blocking error: correct file and upload again
```

Uploading alone does not create green-space records. Validation stores its results and row counts. Only an explicit confirmation after successful validation imports the entire dataset. This follows the report's requirement to block import until errors are corrected.

The column names, 5 MiB/1,000-record limits, and owner-only access rule below are implementation choices for this first version, not additional requirements quoted from the report.

## 1 Complete the earlier prerequisites

Open PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis'
.\.venv\Scripts\python.exe .\scripts\check_setup.py
.\.venv\Scripts\python.exe .\scripts\verify_database.py
```

Both checks must pass before using the endpoints. If not, complete [Step 1](STEP-1.md) and [Step 2](STEP-2.md). Then follow [Step 3](STEP-3.md) to create the administrator account and verified administrative-area/category records.

Start the backend, leaving the terminal running:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

## 2 Prepare the CSV

Use a UTF-8, comma-separated `.csv` file. An optional UTF-8 BOM is accepted. Limits are 5 MiB and 1,000 data records per file. Do not rename an Excel workbook to `.csv`; export its contents as CSV. Blank records are ignored.

The downloadable template has this header:

```text
name,area_id,category_id,area_size,facilities,description,latitude,longitude,geometry_wkt
```

| Column | Required value / meaning |
|---|---|
| name | Required; up to 150 characters |
| area_id | Required; an existing administrative-area ID |
| category_id | Required; an existing category ID |
| area_size | Optional, non-negative hectares; up to 4 decimal places |
| facilities | Optional text; up to 20,000 characters |
| description | Optional text; up to 20,000 characters |
| latitude | -90 to 90; up to 6 decimal places |
| longitude | -180 to 180; up to 6 decimal places |
| geometry_wkt | Optional plain WKT; POINT, POLYGON, or MULTIPOLYGON |

The three name/ID columns must be present. Optional columns may be omitted, but the header must contain both coordinate columns or geometry_wkt. Unknown and duplicate headers are rejected to catch typing mistakes.

For point-only records, fill latitude and longitude and leave geometry_wkt blank. For polygon records, supply valid WGS84 (EPSG:4326) WKT and either leave both coordinates blank or supply both as reference coordinates. WKT must be two-dimensional and have no `SRID=...;` prefix. If a POINT WKT and coordinate values are both supplied, they must agree to six decimal places. Geometry coordinates use longitude first, latitude second.

Check and reproject source data in QGIS before export. Assigning EPSG:4326 to coordinates from a different system is not reprojection. Range and geometry checks do not prove that a park lies inside Petaling, is publicly accessible, or has the stated area; those still require approved source data. Area values are not automatically calculated in this step.

Synthetic example, only for a disposable test database:

```csv
name,area_id,category_id,area_size,facilities,description,latitude,longitude,geometry_wkt
TEST example - not real park data,1,1,1.2500,Test only,Synthetic fixture,3.100000,101.600000,
```

Replace the example IDs with existing reference IDs. Never use the example as real research data. Quote fields containing commas, quotes, or newlines; normal CSV exports handle this. A polygon's WKT normally contains commas, so its whole field must be quoted.

## 3 Sign in using Postman

Use the Step 3 Postman login procedure and retain its cookies. Keep the hostname `127.0.0.1` throughout.

GET `http://127.0.0.1:8000/api/admin/session/` after login. Copy `csrf_token` and send it as the `X-CSRFToken` header on every POST below. The session response now also includes dataset_permissions. Do not disable CSRF protection or share session cookies.

The first development superuser has the required permissions. A limited CSV administrator needs:

- DatasetUpload: view, add, and change.
- GreenSpace: view for session/lookups; add for confirmed import.
- Active and Staff status.

Limited administrators can access only their own uploads. The application superuser can access all uploads. Green-space edit/delete permissions remain separate, as in Step 3.

## 4 Upload, validate, then confirm

### A Get the template and reference IDs

GET `/api/admin/datasets/template/` downloads a header-only template. GET `/api/admin/lookups/` provides valid area/category IDs. Add your verified data to a local copy of the template.

### B Upload the file

POST `http://127.0.0.1:8000/api/admin/datasets/`.

In Postman choose **Body > form-data**, add a key named **file**, change its type from Text to **File**, and select your CSV. Keep the CSRF header, but remove any manually set Content-Type header: Postman needs to generate the multipart boundary itself. Django receives uploaded files through a multipart request. See [Django file uploads](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/).

Expected: HTTP 201, a dataset_id, and status `uploaded`. Copy the returned ID. No green-space rows are inserted at this point. Basic extension, size, encoding, and binary-content checks happen during upload; detailed CSV checks happen next.

### C Validate

POST `/api/admin/datasets/<dataset_id>/validate/`, with no body and the CSRF header. Replace the placeholder with your actual ID.

The HTTP 200 response describes the validation result; 200 does not mean the data passed. Check:

- `status`: `validated` or `invalid`.
- `ready_to_import`: true only when no blocking errors remain.
- `total_records`, `valid_records`, and `invalid_records`.
- `issues`: row number, field, message, and severity.
- `validation_token`: supplied only when validation succeeds.

Row numbers count CSV records with the header as record 1; multiline quoted fields do not create extra records. File-level structure errors use `_file`, no row number, and zero counts because a reliable complete row count is unavailable. A row with several errors counts as one invalid record. Results show up to 100 issues per page; GET the dataset detail with `?page=2` for more.

If errors exist, correct your local CSV and upload it again. This is the backend behavior for Figma's **Replace File** action: it creates a new dataset ID, preserving the previous upload. Revalidating the same dataset refreshes its stored validation issues. It does not import records.

### D Confirm import

Only after reviewing a successful validation, POST `/api/admin/datasets/<dataset_id>/import/` using **Body > raw > JSON**:

```json
{"validation_token": "paste-the-token-from-successful-validation"}
```

Use `Content-Type: application/json`, the session cookies, and the CSRF header. The validation token is different from the CSRF token. It expires after 24 hours; validate again if it expires.

Expected: HTTP 200, status `imported`, and imported_records. View the resulting records through Step 3's administration pages or record endpoints. Each imported record links back to its DatasetUpload.

Confirmation checks that the staged file matches the validated file, checks the data again, and imports all rows in one database transaction. An insertion failure rolls back the whole import. This uses [Django's transaction support](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

Retrying confirmation for the same dataset returns `already_imported: true` without adding more records. This does not deduplicate separately uploaded files against existing parks: do not upload an already imported dataset under a new ID. Duplicate rows with the same case-insensitive name, area, category, and serialized geometry are rejected within a file. Geometrically equivalent polygons with different vertex ordering may not count as identical in this initial duplicate check.

## Endpoint summary

| Method | Path | Result |
|---|---|---|
| GET | `/api/admin/datasets/template/` | Blank CSV template |
| GET / POST | `/api/admin/datasets/` | Upload history / upload one CSV |
| GET | `/api/admin/datasets/<id>/?page=1` | Status, counts, validation errors |
| POST | `/api/admin/datasets/<id>/validate/` | Validate without importing |
| POST | `/api/admin/datasets/<id>/import/` | Explicitly confirm the import |

History shows 50 uploads per page. Invalid request data returns 400; authentication/permission/CSRF errors return 401 or 403; unavailable or inaccessible IDs return 404; conflicts return 409; oversized streamed uploads return 413; incorrect request content types return 415. Storage or caught database failures return 503. After a timeout, check the existing dataset's status before retrying; do not create another upload to retry confirmation.

## Private files and scope

Source CSVs are stored locally under `backend/media/private_uploads/<dataset_id>.csv`. Uploaded filenames are display metadata, not filesystem paths. This directory is ignored by Git and has no public file-serving route. Do not expose it through a web-server media alias. Keep its backup consistent with the database.

Invalid uploads remain available for audit; no retention/deletion workflow is added here. Import adds records only: it never updates or replaces existing parks. This stage does not implement public maps, nearby search, accessibility calculations, dashboard indicators, reports, or the final Figma interface.

## Run the tests

The helper tests can run now:

```powershell
Push-Location .\backend
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
Pop-Location
```

After completing native GIS/database setup, initial migrations, and Step 3's dedicated disposable PostGIS test database:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py test greenspaces --keepdb
```

The 17 new integration tests cover staging without import, all-or-nothing validation, geometry, repeat confirmation, token/file mismatches, changed references, rollback, upload ownership, permissions, CSRF, and stored results. Together with Step 3, there are 31 database integration tests. They are written, not yet passed or verified on PostGIS.

```text
backend/greenspaces/
  csv_schema.py          CSV structure, scalar values, and limits
  upload_limits.py       Streaming file-size guard
  dataset_storage.py    Private staged source files
  datasets.py           Validation and transactional import
  upload_views.py       Upload/history/validate/import endpoints
  test_datasets.py      PostGIS integration tests
backend/helper_tests/
  test_csv_schema.py     Parser tests without a database
  test_dataset_storage.py  Private-file and upload-limit tests
```

Step 4 is verified only after the integration tests and an end-to-end import succeed in the configured environment. The code preparation alone does not complete that checkpoint.
