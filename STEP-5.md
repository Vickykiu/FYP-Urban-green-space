# Stage 5 Public interactive map

Stage 5 implements the public map and green-space details for FR1/FR4 using your proposed React, Leaflet, Django/GeoDjango, and PostgreSQL/PostGIS stack. The map, error dialog, and details drawer follow the prototype screenshots in FYP.docx and the supplied Figma reference.

The frontend can be opened without signing in. **The live database is not ready:** PostgreSQL/PostGIS and native GIS libraries are not installed, schema migrations have not been applied, and no administrator account or project parks have been created. The map therefore reports the connection error rather than inventing successful data access.

## Open Stage 5

In PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis\frontend'
npm.cmd run dev
```

Open [the local public map](http://127.0.0.1:5173/). If the server is already running, use that page instead of starting a duplicate.

Until Django/PostGIS is connected, the prototype's **Map could not be loaded** dialog appears. Select **Close** to inspect the interface and locally bundled Petaling district boundary. Its attribution explicitly says **local seed**. Category counts remain dashes, not misleading zero counts. The information icon reopens the error; **Retry** checks the connection again. This is a local development preview, not an internet deployment.

## Prototype alignment

- Sidebar labels, map title/subtitle, search placeholder, layer labels, category names/order, selected-record labels, and action labels follow the reference. The local SVG icons use the reference's tree, grid, map, search, target, chart, report, and login symbols. These are recreated vectors, not exported Figma assets; pixel-identical source-asset fidelity has not been verified.
- Removed the extra “Later stage” badges, “Petaling view” text button, database-count explanatory text, extra category row, browse picker, and sidebar footer.
- The error dialog uses the reference wording, tinted backdrop, Attention box, and **Retry / Close** buttons. New empty-results, detail-error, and result-limit states reuse that format. Dialogs support keyboard focus and Escape.
- **View green-space details →** opens the reference-style **Green-Space Details** drawer with Name, Type, Area, District, Facilities, Description, and **View on Map**.
- Operating hours retain the prototype label, but display **Not provided** because the current ERD/CSV contract has no opening-hours field. The image area is the prototype's neutral placeholder, not an invented park photo.
- Prototype example names, counts, opening hours, roads, and green polygons are not treated as real geographical records. Analysis layers and later-stage actions stay disabled; Priority areas is off because there is no calculated priority layer yet.

The **Search location...** placeholder is preserved. In this stage it filters uploaded green-space names within the visible map, not street addresses or device location. Enter submits the search; clearing the field removes it. Clicking a selected category again removes that filter.

## Data flow and Petaling seed

There are **no OpenStreetMap tiles or OSM data imports**. Leaflet supplies interaction and displays your project's GeoJSON on the prototype's mint background. Green-space records are supplied through the administrator CSV upload → validation → explicit import flow from [Step 4](STEP-4.md). Uploading or validating alone does not publish records.

The bundled district boundary comes from the [DOSM district dataset](https://github.com/dosm-malaysia/data-open/blob/21a78e98efd4cd9b022a27a1bf67d167076b7591/datasets/geodata/administrative_2_district.geojson). Only Petaling, Selangor is extracted; its coordinates are unchanged. It is a simplified district reference, not a cadastral survey. Provenance and redistribution terms are in `data/`.

Once [Step 1](STEP-1.md) prerequisites and [Step 2](STEP-2.md) schema migrations are complete, run from the project root:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py seed_petaling
.\.venv\Scripts\python.exe .\scripts\verify_database.py
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

`seed_petaling` is an explicit reference-data command to run **after migrations**, not a schema migration. It creates the district and four category labels, preserves existing data, rejects ambiguous duplicates, and prints actual IDs for CSV uploads. It does not create sample parks. See [seed notes](data/README.md).

After real CSV records have been imported, use **Retry** or reload the public map. Public routes do not require login; the existing administrator write/upload routes retain authentication and permission checks.

## Public endpoints

| Method | Path | Result |
|---|---|---|
| GET | `/api/public/green-spaces/` | Paginated green-space GeoJSON |
| GET | `/api/public/green-spaces/<id>/` | Public details and geometry |
| GET | `/api/public/administrative-areas/` | Administrative-boundary GeoJSON |
| GET | `/api/public/map-options/` | Categories and actual database counts |

List parameters are `bbox=west,south,east,north` and `page`. Green-space queries also accept `q` and `category`. Geometry uses WGS84 longitude/latitude; bounding-box filtering uses spatial intersection. Responses contain up to 200 features per page. The frontend follows up to ten pages and shows a result-limit dialog when needed. Superseded requests are cancelled.

Public writes return 405; invalid parameters return 400; missing details return 404; database failures return 503. Uploaded names/descriptions are rendered as text, never executable HTML. Public responses exclude account, password, upload-owner, and private dataset metadata.

## Verification

The latest checks passed: **13 frontend tests**, **36 database-independent backend tests**, and the production build. Browser checks used an isolated, prominently labelled synthetic test API and covered marker/polygon selection, keyboard polygon access, category filtering/reset, details, retry/close, empty results and clearing filters, and mobile layout/navigation. The normal page was separately checked without Django: it showed the sourced local boundary and the connection error, with no sample parks.

**46 PostGIS integration tests are written but unrun**, including three seed tests. No migration, seed application, real CSV import, spatial database accuracy test, or representative-data performance test has passed on this machine yet.

Frontend checks from `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

Backend helper checks from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
```

After native setup, migrations, and Step 3's disposable PostGIS test database:

```powershell
..\.venv\Scripts\python.exe manage.py test greenspaces --keepdb
```

For UI-only testing, start `scripts/serve_map_test_fixture.py` using the project virtual environment. In a separate frontend terminal, set `$env:GIS_DEV_API_TARGET = 'http://127.0.0.1:8015'` and run `npm.cmd run dev -- --port 5175 --mode ui-test`. The page must show the **UI TEST — SYNTHETIC DATA** banner. Search `UI_TEST_ERROR` to test failure, or an absent name for the empty state. This test server never writes to the project database and must not replace Django in the normal app. Stop both test processes after use and clear that temporary environment variable before restarting normal development.

Stage 5's interface work is ready for review. End-to-end Stage 5 completion still requires the missing database/GIS installation, migrations, seed application, verified CSV records, and passing PostGIS tests. [Stage 6](STEP-6.md) now enables the Search nearby page and location-selection flow; its guide contains the current combined test totals and remaining address-lookup limitation. Accessibility analysis remains a later stage.
