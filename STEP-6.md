# Stage 6 Location selection and nearby green-space search

This stage implements the location-selection and nearby-search interface and backend code for FR2/FR3. It uses the existing React, Leaflet, Django/GeoDjango and PostgreSQL/PostGIS stack. It does not add a geocoding provider, an alternative database, Docker, OpenStreetMap tiles or OSM imports.

**Status:** interface and database-independent checks pass; live database verification remains blocked. PostgreSQL/PostGIS and the native GIS libraries still need installation/configuration, and the database password must be entered locally. No migrations, database seed, administrator account or real CSV import have been applied. General street-address lookup remains pending, so FR3 is only partially implemented.

## Open the public interface

If the preview is already running, open [Nearby green-space search](http://127.0.0.1:5173/#nearby). Otherwise start it in PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis\frontend'
npm.cmd run dev
```

No public-user login is required. Select **Search nearby** in the sidebar, then:

1. Select **STARTING LOCATION** or **Search location...** to open **Select Location**.
2. Choose a point on the map, enter `latitude, longitude`, or find an administrator-maintained green-space name. Map keyboard users can pan with the arrow keys and press Enter to select the centre. **Use current location** requests browser permission only after it is clicked.
3. Check the selected name and coordinates, then select **Confirm Location**. **Cancel** leaves the previous search unchanged. Editing the text invalidates the unconfirmed selection.
4. Choose **500 m**, **1 km**, **2 km**, or **Custom**. Custom distances must be whole metres from 100 to 10,000; these are implementation safety limits, not quoted proposal requirements.
5. Select **Search nearby**. Results are sorted by distance, shown on the map, and have **View details** / **View on Map** actions. Changing the location or radius clears stale results and cancels the previous request.

Without Django/PostGIS, map/coordinate selection can be inspected using the attributed local Petaling boundary. Searching records reports an unavailable-service error, not successful empty results or example parks. Location permission also requires a supported secure browser context; no device location was accessed during development testing. [Browser geolocation requirements](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition).

## Following the report and prototype

The nearby page, **Select Location**, and **Location not found** screens follow the report's prototype screenshots and [supplied Figma reference](https://www.figma.com/design/WvnlAkodH423nIUpDd5mv0/Untitled?node-id=0-1). Existing sidebar wording, vector symbols, colours, cards, buttons and dialog styling are retained. New unavailable-service, invalid-radius and empty-result screens reuse the prototype's error format. Icons remain recreated vectors, not exported Figma source assets; pixel-identical fidelity is not certified.

The proposal includes address input but names neither a street-address dataset nor a geocoding service. Consequently, **Address or place** currently searches uploaded green-space names, not arbitrary street addresses. An unmatched address produces the prototype's location-not-found screen with an explanation and map-selection alternative. No external address service has been added without a report-based choice.

Prototype example walking minutes and **Open now** cannot be presented as measured facts: the current data has neither a routing calculation nor opening hours. Cards therefore use **Straight-line distance** and **Hours not provided** in the same positions and styling. The **Analyse →** and **Continue with selected location / Generate distance-based coverage** controls now open [Stage 7](STEP-7.md), carrying the confirmed starting location and chosen radius. Analysis requires an explicit **Run analysis** click. The nearby page's search-radius circle itself is not a computed accessibility-coverage or walking-network layer.

## Data and distance rules

- Park records still come from administrator **CSV upload → validation → explicit import**, as described in [Step 4](STEP-4.md). Uploading alone does not publish data. No parks have been seeded or downloaded from OSM.
- The starting location must be inside or on the Petaling district boundary. The browser checks the bundled DOSM snapshot; the backend checks the configured database boundary. Keep these boundaries aligned if the reference is replaced. Missing or ambiguous database district configuration is an explicit error.
- Candidate parks must intersect the configured district. Distance is measured to the nearest point of each whole stored park geometry, not its centroid or an assumed entrance. A point inside a polygon has zero distance; a point inside a polygon hole does not.
- The backend casts WGS84 geometry to geography for metre-based radius filtering and distance ordering. It uses full precision for filtering and only rounds the displayed label. This follows [PostGIS ST_DWithin](https://postgis.net/docs/ST_DWithin.html), [PostGIS ST_Distance](https://postgis.net/docs/ST_Distance.html), and [GeoDjango Distance](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/functions/#distance). The implementation still needs execution against PostGIS to verify its spatial results.
- Responses contain at most 200 records per page. The frontend follows up to ten pages and explicitly reports a display limit above 2,000 records. Place lookup returns up to ten matches.
- Location searches are anonymous, read-only POST requests with Django CSRF protection. Coordinates and typed place names are in JSON bodies rather than URL query strings; the application does not save location history. Search responses use `Cache-Control: no-store`. Deployment logging must also avoid recording sensitive request bodies.

## Backend endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/public/nearby/options/` | CSRF token, radius limits and supported lookup methods |
| POST | `/api/public/locations/search/` | Find uploaded names using `{ "q": "place name" }` |
| POST | `/api/public/nearby/` | Search with `latitude`, `longitude`, `radius_m`, optional `page` |

POST clients must keep the CSRF cookie from the options response and send its `csrf_token` as `X-CSRFToken`. An administrator session is not required. Invalid searches return 400, missing CSRF returns 403, wrong methods return 405, and unavailable database/study-area data returns 503. Normal searches do not create or modify records.

## Connect real data after prerequisites are ready

From the project root, check the environment:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_setup.py
```

Only after every check passes, follow [Step 2](STEP-2.md) to generate, review and apply the initial schema migrations. Then run:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py seed_petaling
.\.venv\Scripts\python.exe .\scripts\verify_database.py
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

`seed_petaling` creates reference district/category records after migrations, not sample parks. Set up an administrator using [Step 3](STEP-3.md), then validate and explicitly import approved CSV records using [Step 4](STEP-4.md). Check the public nearby page without logging in. Never paste database or administrator passwords into chat.

## Verification

Checked on 28 September 2026:

- **27 frontend tests passed**, including coordinate/district/radius validation, injected geolocation success and errors, request privacy, CSRF-token forwarding, cancellation, pagination, ordering and result limits.
- **43 database-independent backend tests passed**, including seven new nearby-query tests. The frontend production build also passed.
- Isolated browser checks covered confirmation/cancel, local place-name lookup, outside-district and unknown-address errors, 1 km and custom-radius searches, sorted cards, details, empty results, retry, stale-result clearing, keyboard selection, and a 390-pixel mobile layout. A search-circle zoom error and initially off-centre dialog map were found and corrected.
- **59 PostGIS integration tests are written but unrun**, including 13 nearby tests for metre distances, polygon holes, radius edges, pagination, CSRF and public read-only access. The browser fixture uses approximate synthetic distances; it is not evidence of PostGIS accuracy.
- The report's three-second performance target has **not** been benchmarked on representative data. Current code has a district geometry filter; any additional geography-expression index should follow actual query profiling.

Frontend checks:

```powershell
Set-Location .\frontend
npm.cmd test
npm.cmd run build
```

From `backend/`, helper checks:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
```

After native setup, schema migration files, and the dedicated disposable PostGIS test database described in Step 3:

```powershell
..\.venv\Scripts\python.exe manage.py test greenspaces --keepdb
```

For UI-only checks, use the labelled synthetic server described in [Stage 5](STEP-5.md). On port 5175, select `3.08,101.60`: 1 km returns one synthetic park; 5,000 m returns three. Radius 777 deliberately returns a service failure. `TEST Alpha` matches an uploaded-place fixture; an unlisted address returns no match. These values belong only to the test fixture, which must never replace Django in the normal preview or be imported into the research database. Stop the test servers after checking.

## Changed-file guide

```text
backend/
  config/urls.py                         Public search routes
  greenspaces/nearby_queries.py          Strict, database-independent validation
  greenspaces/nearby_views.py            Read-only PostGIS searches
  greenspaces/test_nearby.py             Spatial integration tests (unrun)
  helper_tests/test_nearby_queries.py    Validation tests
frontend/src/
  NearbyPage.jsx                        Search page and request lifecycle
  location.js                           Coordinates, district checks, device adapter
  nearbyApi.js                          CSRF-protected search and pagination
  components/LocationDialog.jsx         Explicit location selection/confirmation
  components/NearbyDetails.jsx          Existing-prototype details panel
  components/GreenMap.jsx               Origin, radius and point selection
```

Stage 6 is ready for interface review, not complete end-to-end acceptance. Remaining gates are native database/GIS setup, real imported data, passing spatial integration tests, representative performance checks, and the report's unresolved general-address lookup requirement. Continue with [Stage 7 accessibility coverage](STEP-7.md) for the implemented interface, calculation definitions and remaining verification gates.
