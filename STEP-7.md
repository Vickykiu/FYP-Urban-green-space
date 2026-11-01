# Stage 7 — Distance-based accessibility coverage

This stage prepares the public accessibility-analysis interface and backend for FR5 / Table 4.6 of the report. It uses the existing React, Leaflet, Django/GeoDjango and PostgreSQL/PostGIS stack. Park data still comes from **administrator CSV upload → validation → explicit import**. No OpenStreetMap park data, tiles, external geocoder or population provider has been added.

**Status:** interface, helper tests and production build pass. The PostGIS implementation is written but has not been run against a spatial database. PostgreSQL/PostGIS, native GIS libraries and local database credentials remain prerequisites. No migrations, district seed, administrator account or actual park import have been applied. Population coverage is not implemented without a suitable dataset and agreed calculation method; FR5 is therefore not fully accepted.

## Open and use the page

Open [Accessibility coverage](http://127.0.0.1:5173/#accessibility) while the normal frontend preview is running. To start it in PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis\frontend'
npm.cmd run dev
```

1. Choose **Accessibility** in the sidebar or **Run accessibility** on the interactive map.
2. Select **SELECTED LOCATION** or **Search location...**. Choose a point within Petaling District and select **Confirm Location**. The existing map, typed-coordinate, uploaded-place-name and user-invoked device-location options are retained. General street-address lookup remains pending as explained in Stage 6.
3. Select **500 m**, **1 km**, **2 km**, or expand **Custom distance**. Custom values must be whole metres from 100 to 10,000. These limits are implementation safeguards, not values quoted from the report.
4. Select **Run analysis**. Results are not generated automatically. Changing a confirmed location or the distance cancels outstanding work and clears old results.
5. Inspect the coverage bands, reached parks and **Coverage results**. Park map popups retain their details action. **Analysis failed** offers the prototype's **Retry** and **Back**; Back opens location selection.

From nearby search, **Analyse →** and **Continue with selected location / Generate distance-based coverage** carry the confirmed starting location and radius to this page. The selected park does not silently replace the user's starting location. No public login is needed. **Open dashboard** now opens [Stage 8](STEP-8.md), which uses an independent 1 km threshold for administrative-area summaries, not this page's personal origin or custom distance.

Without Django/PostGIS, the page shows the attributed local Petaling boundary and a service error when analysis is requested. It never displays synthetic parks or successful measurements in the normal preview.

## Prototype and report alignment

The page follows the report's accessibility-coverage and analysis-failed screens and the [supplied Figma reference](https://www.figma.com/design/WvnlAkodH423nIUpDd5mv0/Untitled?node-id=0-1): existing navigation, titles, icon symbols, green buttons, distance controls, three result cards, legend and planning interpretation are retained. Custom-distance input and unavailable-data explanations use the existing visual style. Icons are recreated SVGs, not exported Figma assets; pixel-identical fidelity is not certified.

Example numbers in the prototype are not research data. **Population covered** displays **Unavailable**, and **PRIORITY GAP** remains unassessed. No resident counts, service-coverage percentages, walking times or priority rankings are fabricated.

## What the measurements mean

These are explicit implementation definitions where the report does not prescribe the exact calculation:

| Display | Calculation / limitation |
|---|---|
| Coverage bands | Buffers at 500 m, 1 km, 2 km and the chosen custom distance, clipped to the configured Petaling district. They are nested catchments, not travel-time zones. |
| Green spaces reached | Number of uploaded park records whose nearest whole-geometry distance from the origin is at most the selected radius. Candidate records must intersect Petaling. Duplicate records count separately; data quality must be checked during import. |
| Change vs 500 m | Selected-radius record count minus the 500 m count. A distance below 500 m can produce a negative change. |
| Total accessible area | Hectares of reached **mapped park polygons inside the district-clipped catchment**, with overlapping footprints dissolved to avoid double-counting land. This is green-space area, not the entire circular catchment. |
| Percentage of zone | Mapped accessible green-space area divided by the district-clipped catchment area. Mixed point/polygon data is marked **mapped polygons only**. |
| Catchment area | All land inside the selected district-clipped buffer, in hectares, shown separately in **Planning interpretation**. This does not mean all that land is green space. |
| Population covered / priority gap | Unavailable. No population dataset, demographic model or allocation method is configured. Unknown is not zero. |

Point-only parks contribute to counts but not to invented footprint areas. With only reached point records, accessible area is **Unavailable**. With mixed data, it is a partial polygon-only measurement. A successful search reaching no parks returns count **0** and mapped area **0 ha**. A completely missing district park dataset is an error, not a successful zero result. The optional CSV `area_size` value is not substituted for a missing mapped footprint because its overlap with the catchment cannot be determined.

The backend uses geography [ST_Buffer](https://postgis.net/docs/ST_Buffer.html), which chooses a local planar projection and approximates a circle (64 segments per quadrant here). Park reach uses spheroidal geography distance, consistent with nearby search. Footprints are clipped using [ST_Intersection](https://postgis.net/docs/ST_Intersection.html), dissolved, then measured with geography [ST_Area](https://postgis.net/docs/ST_Area.html) in square metres and converted to hectares. Near a distance threshold the drawn approximate buffer can differ slightly from the exact-distance inclusion test. Spatial accuracy still requires the unrun PostGIS tests.

A park crossing the district boundary is counted using its whole stored geometry; only its footprint inside the district catchment contributes to measured area. Distances are not to assumed entrances. Routes, barriers, opening hours, public entry restrictions and network travel times are not evaluated. Keep the browser's bundled district snapshot and the database study-area boundary aligned.

## Public backend contract

`POST /api/public/accessibility/` accepts only:

```json
{ "latitude": 3.08, "longitude": 101.60, "radius_m": 1000 }
```

The coordinates above are a test input, not a real user's location. Clients first obtain `/api/public/nearby/options/`, retain its CSRF cookie and send the returned `csrf_token` as `X-CSRFToken`. An administrator session is not required. Coordinates are sent in a JSON body, not the URL. Searches are read-only, do not save location history, and return `Cache-Control: no-store`; deployment logging must also avoid sensitive request bodies.

The response contains `coverage` GeoJSON, nullable `metrics`, reached `green_spaces` GeoJSON and calculation limitations. A single parameterized analysis statement keeps park counts, displayed records and bands consistent. At most 2,000 parks are drawn; indicators include every reached record, and truncation is explicitly reported. The statement has a five-second resource timeout; this is **not** proof of the report's three-second performance target.

Invalid coordinates, distance or extra fields return 400; missing CSRF returns 403; wrong methods return 405. Missing/ambiguous district configuration, a missing park dataset, or an unavailable spatial database returns 503. Internal database errors are not exposed to the public.

## Connect the real database

From the project root:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_setup.py
```

Complete [Step 1](STEP-1.md) first. After setup passes, generate, review and apply the initial migrations using [Step 2](STEP-2.md), then:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py seed_petaling
.\.venv\Scripts\python.exe .\scripts\verify_database.py
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

The seed creates reference district/category records, not example parks. Create the administrator using [Step 3](STEP-3.md), then validate and explicitly import approved park CSV data through [Step 4](STEP-4.md). Stage 7 adds no database model or migration of its own. The earlier initial migrations are still required. Keep passwords local; do not send them through chat.

## Verification and remaining gates

Checked on 29 September 2026:

- **36 frontend tests passed**, including nine coverage tests for strict response validation, custom bands, point-only area handling, zero versus unknown values, cancellation, request privacy and CSRF forwarding.
- **49 database-independent backend tests passed**, including six coverage validation/metric tests. The production build and Python syntax checks passed.
- Isolated browser checks covered missing-origin selection, preset and custom distances, point-only and mixed-footprint displays, valid zero results, error Retry/Back, cancellation/stale-result clearing, nearby-to-analysis transfer and a mobile-width layout with no horizontal overflow. These checks used a conspicuously labelled synthetic service.
- **71 PostGIS integration tests are written but unrun**, including 12 coverage tests for area units, overlapping polygons, district clipping, exact distance thresholds, nullable population, limits, anonymous CSRF-protected access and failure states.
- No real GIS calculation, import, migration, performance benchmark or production deployment has been completed. Browser fixtures are not proof of spatial correctness. Population coverage, representative-data performance and end-to-end acceptance remain outstanding.

From `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

From `backend/`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
```

Only after native setup, initial migrations and the dedicated disposable PostGIS test database described in Step 3:

```powershell
..\.venv\Scripts\python.exe manage.py test greenspaces --keepdb
```

### UI-only fixture

Use the separate, labelled test servers described in [Stage 5](STEP-5.md), never the normal preview or research database. On port 5175:

- `3.08,101.60`, 1 km: one point-only synthetic park, accessible area unavailable.
- The same location, 5,000 m: three synthetic records and a deliberately illustrative partial polygon area.
- Radius 777: deliberate service failure for Retry/Back checks.
- Radius 888: delayed response for cancellation checks.
- `3.06,101.60`, 100 m: successful zero parks and zero mapped green-space area.

The fixture uses approximate circles and illustrative area values; it does **not** execute PostGIS, clip against the real district or verify geography measurements. Stop its servers after testing. Do not import it into the research database.

## Changed-file guide

```text
backend/
  config/urls.py                       Public accessibility route
  greenspaces/coverage_queries.py     Strict input validation and metric contract
  greenspaces/coverage_views.py       Parameterized read-only PostGIS calculation
  greenspaces/test_coverage.py        Spatial integration tests (unrun)
  helper_tests/test_coverage_queries.py
frontend/
  src/AccessibilityPage.jsx           Coverage page and request lifecycle
  src/coverageApi.js                  CSRF request and response validation
  src/components/GreenMap.jsx         Nested coverage layers
  src/App.jsx                        Public navigation and map handoff
  src/NearbyPage.jsx                  Confirmed-location/radius handoff
  tests/coverageApi.test.js
```

Stage 7 is ready for interface review, not complete end-to-end acceptance. Continue with [Stage 8's planning dashboard](STEP-8.md) for its available indicators and remaining data/verification gates.
