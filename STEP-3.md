# Step 3 Administrator access and green-space record management

This stage prepares the backend for the report's administrator-only record management (FR10): add, view, edit, search, and delete green-space records. It uses Django/GeoDjango and PostgreSQL/PostGIS from your proposed stack, with no additional REST framework or Docker.

Current status: the code is prepared and the database-independent helper tests pass. The application has not been run against PostGIS because Step 1 still needs native GIS libraries and a configured database password. Step 2 migrations are not yet generated or applied. No administrator account or green-space records have been created by this work.

The built-in Django administration pages are a development tool, not the final interface. The React interface will follow your supplied Figma design in a later step. CSV uploads, accessibility calculations, dashboards, and reports are not implemented in this stage.

## 1 Finish the database prerequisites

Open PowerShell in the project folder:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis'
.\.venv\Scripts\python.exe .\scripts\check_setup.py
.\.venv\Scripts\python.exe .\scripts\verify_database.py
```

Continue only when both checks succeed. Follow [Step 1](STEP-1.md) for installations and [Step 2](STEP-2.md) to create and verify the tables. If either command reports missing prerequisites, do not create an account yet.

## 2 Create your first administrator

From the same project folder:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py createsuperuser
```

Enter a username, email address, and a strong password when prompted. The password is intentionally not displayed. Keep it private; do not paste it into chat or source code. Django stores a password hash, not the plain-text password. See [Django's administrator-account guidance](https://docs.djangoproject.com/en/5.2/topics/auth/default/#creating-superusers).

This is your application administrator, separate from the PostgreSQL `postgres` or `petaling_app` database accounts. The initial development account has full application permissions. Use the username to sign into the temporary Django administration pages; the custom Figma login screen is not built yet.

## 3 Start and open the backend

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

Leave that terminal running. Open [local administration](http://127.0.0.1:8000/admin/) and sign in. The heading should be "Petaling GIS administration".

The page provides access to administrator accounts, administrative areas, green-space categories, and green spaces. This is a local development server, not a public deployment.

## 4 Prepare the reference records

Each green space requires an administrative area and a category, matching the report's ERD.

- Add the categories approved for your project under **Green space categories**.
- An **Administrative area** needs its name and a valid polygon or multipolygon boundary. Use a verified boundary from your approved spatial dataset; do not treat a roughly drawn polygon as an official Petaling boundary.
- If you do not yet have verified boundary data, stop before entering real green-space records. The automated integration tests below use explicitly synthetic boundaries in a separate test database.

The administrative-area development form has a GIS map widget. Automated import of reference boundaries is not part of this step.

## 5 Add, view, edit, and delete green spaces

In **Green spaces**, choose **Add**. Supply:

| Field | Rule |
|---|---|
| Name | Required; up to 150 characters |
| Administrative area | An existing reference record |
| Category | An existing category |
| Area (ha) | Optional, non-negative hectares; up to 4 decimal places |
| Facilities / Description | Optional text |
| Latitude | Required for a new manual point; -90 to 90; up to 6 decimal places |
| Longitude | Required for a new manual point; -180 to 180; up to 6 decimal places |

Saving creates WGS84 point geometry from longitude and latitude. Range checks do not establish that a point lies inside Petaling; use verified locations. Point records alone do not represent a park's complete boundary, and the entered hectare value is not calculated from a point.

The list supports name/description search and administrative-area/category filters. Open a record to view or edit it. Changing a point's coordinates updates its geometry. Editing a pre-existing polygon record preserves its boundary; its latitude and longitude may both be blank. The upload-dataset link is read-only here and remains empty for a new manual record.

The development administration pages ask for confirmation before deleting a record. Delete only a record you intend to remove: deletion is permanent unless you have a database backup. No records are deleted automatically by this guide.

For a limited administrator, create a separate user with **Active** and **Staff status**, then grant only the required GreenSpace view/add/change/delete permissions. Do not give ordinary data editors account-management or superuser privileges. The API checks each action's permission separately; view permission alone cannot edit or delete.

## 6 JSON endpoints for the later React interface

These backend endpoints use the same Django login session. All are administrator-only:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/session/` | Current username, record permissions, and CSRF token |
| GET | `/api/admin/lookups/` | Area/category IDs and names |
| GET | `/api/admin/green-spaces/?page=1&q=park` | Name search; 50 records per page |
| POST | `/api/admin/green-spaces/` | Add a manual point record |
| GET | `/api/admin/green-spaces/<id>/` | Read one record |
| PUT | `/api/admin/green-spaces/<id>/` | Replace all eight editable fields |
| DELETE | `/api/admin/green-spaces/<id>/` | Delete one record |

`<id>` means the actual record ID. PUT requires name, area, category, area_size, facilities, description, latitude, and longitude. Geometry, record ID, and dataset are read-only. Responses include GeoJSON geometry and decimal values as strings to preserve precision.

Example request body, for a disposable test record only:

```json
{
  "name": "TEST record - not real park data",
  "area": 1,
  "category": 1,
  "area_size": "1.2500",
  "facilities": "Test only",
  "description": "Synthetic development example",
  "latitude": "3.100000",
  "longitude": "101.600000"
}
```

Replace area/category IDs with existing IDs from the lookup endpoint. These example coordinates and attributes are not an identified real park. Do not mix synthetic examples into your final research dataset.

### Check using Postman

Use `http://127.0.0.1:8000` for every request; do not switch between `localhost` and `127.0.0.1`. Keep Postman's cookie jar enabled.

1. GET `/admin/login/`. In Postman's cookies, copy the `csrftoken` value for 127.0.0.1.
2. POST `/admin/login/` using **Body > x-www-form-urlencoded** with `username`, `password`, `csrfmiddlewaretoken` (the copied token), and `next` set to `/admin/`. Enter credentials locally; do not save real credentials in a shared collection. After successful login the cookie jar should contain `sessionid`.
3. GET `/api/admin/session/`. A successful JSON response contains your username and `csrf_token`. Use this newly returned token because login rotates CSRF tokens.
4. For POST/PUT, use **Body > raw > JSON** and `Content-Type: application/json`. For POST/PUT/DELETE, add `X-CSRFToken` with the returned token; keep the session and CSRF cookies enabled.
5. Check list/detail requests, valid creation, invalid-coordinate rejection, editing, and permissions. Only test deletion on your own disposable record. Unlike Django admin's confirmation page, an API DELETE acts immediately.

CSRF protection stays enabled; it is not bypassed for Postman. See [Django's CSRF guidance](https://docs.djangoproject.com/en/5.2/howto/csrf/).

Expected responses include 201 for creation, 200 for successful reads/edits/deletion, 400 for invalid data, 401 for unauthenticated API reads, 403 for insufficient permissions or CSRF failure, 404 for missing records, 405 for unsupported methods, and 415 for non-JSON record bodies. Database conflicts return 409 and database failures caught by the API return 503. An unauthenticated write without a CSRF token may return 403 before the login check runs.

## 7 Run the tests

The small helper suite does not require PostGIS:

```powershell
Push-Location .\backend
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
Pop-Location
```

The integration suite needs working GIS libraries, Step 2's migration files, and a separate PostGIS test database. It covers login/logout, action permissions, input validation, point-coordinate order, polygon preservation, pagination, editing/deletion, and CSRF protection.

Using PostgreSQL SQL Shell as the database administrator, create a dedicated disposable database only if it does not already exist:

```sql
CREATE DATABASE test_petaling_green_gis OWNER petaling_app;
\connect test_petaling_green_gis
CREATE EXTENSION IF NOT EXISTS postgis;
```

This name assumes the Step 1 application database is `petaling_green_gis`; Django normally prefixes its name with `test_` for tests. Never use a database containing valuable records as the test database: the test runner changes schema and test data. Enabling PostGIS beforehand lets the application account remain a non-superuser without granting it permission to create arbitrary databases.

Back in the project PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py test greenspaces --keepdb
```

`--keepdb` reuses the dedicated test database. Fixtures use synthetic geometry and test-only accounts, not real parks or production credentials. These integration tests have been written but could not be run in the current incomplete native environment.

## Completion checkpoint

Step 3 is verified only after the prerequisites pass, administrator login works, the integration suite passes, and you can manage approved records with the expected validation and permissions. The final Figma frontend remains unchanged for this step.

Relevant code:

```text
backend/
  config/api.py                 JSON validation, access guards, CSRF errors
  config/urls.py                Endpoint routing
  greenspaces/forms.py          Shared manual-entry validation
  greenspaces/admin.py          Development administration pages
  greenspaces/views.py          Record-management JSON endpoints
  greenspaces/tests.py          PostGIS integration tests
  helper_tests/test_api_helpers.py  Database-independent tests
```
