# Stage 8 — Planning dashboard

The public dashboard interface and backend are prepared for **FR6 / Table 4.8** and **Figure 4.23** of the report. This stage uses React, Chart.js and Django/GeoDjango with PostgreSQL/PostGIS. Park records still come from administrator CSV upload, validation and explicit import. No new data provider, database system or UI framework has been introduced.

**Status:** interface checks, 44 frontend tests, 56 backend helper tests and the production build pass. The 83 PostGIS integration tests across the project are written but unrun. The native database/GIS prerequisites remain incomplete, so real dashboard measurements have not been verified. Population gaps, baseline changes and priority recommendations remain unavailable; this is not complete FR6 acceptance.

## Open the dashboard

With the normal frontend running, open [Planning dashboard](http://127.0.0.1:5173/#dashboard). Otherwise start it in PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis\frontend'
npm.cmd run dev
```

Public users do not need an account. Select **Planning dashboard** in the sidebar, or **Open dashboard** from Stage 7.

1. The page loads available district data using **All areas** and **All categories**.
2. Choose **ADMINISTRATIVE AREA** and/or **GREEN-SPACE CATEGORY**. Changing a selection does not immediately replace the displayed results; a message tells you to apply the filters.
3. Select **Apply filters**. Old results clear while the selected summaries load. Superseded requests are cancelled and cannot overwrite the latest result.
4. Review the four summary cards, area bars and category doughnut. **View coverage values** provides a readable data table, and category counts are listed beside the chart.
5. If data is unavailable, the prototype's **Unable to load dashboard** dialog offers **Retry** and **Close**. Closing does not turn the error into zero or restore stale results. Retry uses the last applied filters. You can choose other filters and apply them.

The dashboard uses the prototype's **1 km distance threshold** for area-wide summaries. It does not reuse a selected person's point or a custom radius from Stage 7. **View full report →** retains the prototype label but remains disabled until the reporting stage.

## Prototype alignment and unavailable information

The interface follows the report's dashboard and dashboard-error images and the [supplied Figma reference](https://www.figma.com/design/WvnlAkodH423nIUpDd5mv0/Untitled?node-id=0-1): the sidebar, page title/subtitle, filter labels, map/grid/target/report symbols, four cards, horizontal coverage bars, category doughnut and priority-table headings remain. Additional explanations and empty/error states use the existing design style. Icons are recreated vectors, not exported Figma assets; pixel-identical fidelity is not certified.

Prototype numbers such as 128 spaces, 78.4% coverage, six planning gaps or a 4.2% baseline increase are **not** used as real data. There is no configured population dataset, historical snapshot or agreed priority threshold/recommendation rule. Therefore:

- **Planning gaps** is **Unavailable** after a successful load, not zero.
- The **Priority planning areas** table keeps its original headings but explains why no ranking or intervention recommendation is generated.
- Historical baseline changes are unavailable; the green-space area card instead explains its mapped-polygon basis.
- Dashboard **Coverage** explicitly means **land area within 1 km of uploaded parks**, not population or residential coverage. This is an implementation definition where the report does not specify the denominator. A population-based indicator requires a separate approved dataset and method.

## Calculation definitions

| Indicator | Definition |
|---|---|
| Administrative scope | All areas means the configured Petaling district. A selected area's polygon is clipped to Petaling. Area options include configured polygons with a positive-area overlap; mere boundary contact is excluded from area options. No ward hierarchy is guessed. |
| Number of spaces | Count of stored green-space records intersecting the selected scope, after the category filter. Spatial intersection determines membership, not just a record's administrative-area foreign key. Boundary contact counts. Duplicate records count separately. |
| Green-space area | Hectares of mapped park polygons clipped to the selected scope and dissolved so overlaps do not double-count land. Point records have no invented footprint. |
| Footprint completeness | Point-only results show **Unavailable** area. Mixed point/polygon results show **Mapped polygons only · partial**. No intersecting records gives **0 ha**. CSV `area_size` is not substituted for a missing spatial footprint. |
| Coverage | Union of 1 km buffers around category-matching parks that intersect Petaling, clipped to the selected scope, divided by the scope's land area. Both point and polygon park geometries contribute buffers. Overlapping catchments count once. |
| Coverage by administrative area | The same land-coverage calculation for each configured area when All areas is selected, or the selected area's value when filtered. Overlapping/hierarchical areas are not additive and must not be summed. |
| Category chart | Count of intersecting park records by their assigned category. Category counts sum to the summary count; configured zero-count categories remain visible. An empty result has a neutral empty ring, not a fabricated distribution. |

Coverage can come from a park just across a selected administrative area's boundary, provided that park intersects Petaling. Consequently, an area can have **zero parks inside it but non-zero covered land**. Parks wholly outside Petaling are not included. No official claim of complete service coverage is made, and outdated/incomplete data affects these indicators.

The backend buffers WGS84 geometries as geography at 1,000 metres with 64 segments per quadrant, unions the catchments, clips them and measures spheroidal geography area. Geography buffering uses a locally chosen projected approximation; it is not a road-network calculation. These calculations follow [PostGIS ST_Buffer](https://postgis.net/docs/ST_Buffer.html), [ST_Union](https://postgis.net/docs/ST_Union.html), [ST_Intersection](https://postgis.net/docs/ST_Intersection.html), and [ST_Area](https://postgis.net/docs/ST_Area.html). Native spatial validation remains outstanding.

The charts use the already selected Chart.js library, with only the required chart components registered and loaded when the dashboard opens. Chart instances are destroyed when their data or page changes. The bar chart's values and category counts have text alternatives, following [Chart.js integration](https://www.chartjs.org/docs/latest/getting-started/integration.html) and [canvas accessibility guidance](https://www.chartjs.org/docs/latest/general/accessibility.html).

## Backend endpoint

```text
GET /api/public/dashboard/
GET /api/public/dashboard/?area=2&category=1
```

The IDs above are illustrative; use IDs returned in the response's `options`. Only `area` and `category` are accepted, each once, as positive integer IDs. Omit a filter for All. Invalid, unknown or out-of-study-area IDs return 400. Wrong HTTP methods return 405. The endpoint is anonymous and read-only; normal application security is not disabled. No personal location or saved search history is involved.

The response contains the applied filters, `options`, `summary`, `areas`, `categories`, a fixed `radius_m: 1000`, and `coverage_basis: land_area_within_park_buffers`. Population/baseline/priority values are explicitly null, with `priority_status: unavailable` and no priority rows. Private upload/account metadata and park geometry are not returned.

Missing/ambiguous Petaling configuration, no park records anywhere in the district, or an unavailable database produces 503. A valid category or area selection with no matching park records can return a successful zero count. All responses from the dashboard handler use `Cache-Control: no-store`. One parameterized aggregate statement keeps displayed totals/charts consistent and avoids per-area request loops. Its five-second statement timeout bounds database work; it does **not** establish compliance with the report's three-second target.

## Connect real data

From the project root, check the existing prerequisites:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_setup.py
```

Finish [Step 1](STEP-1.md), then generate/review/apply initial migrations using [Step 2](STEP-2.md). Stage 8 introduces no new model or migration. After that:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py seed_petaling
.\.venv\Scripts\python.exe .\scripts\verify_database.py
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

The seed creates the sourced district boundary and category references, not parks, subdivisions or population records. Use [Step 3](STEP-3.md) for administrator setup and [Step 4](STEP-4.md) for approved CSV import. Until more verified administrative polygons are configured, the real area comparison will contain only Petaling District. No invented wards are seeded to fill the chart. Keep passwords local.

## Verification

Checked across 29–30 September 2026:

- **44 frontend tests passed**, including eight dashboard tests for filters, cancellation forwarding, response consistency, null versus zero, category totals and prototype error wording.
- **56 backend helper tests passed**, including seven dashboard parameter/metric tests. Production build and Python syntax checks passed.
- Isolated browser checks covered initial charts, unapplied versus applied filters, an area filter, zero results, point-only area, Retry/Close, recovery to valid filters, rapid requests, stale-response rejection, chart remount/navigation, readable chart values and a mobile-width layout without horizontal overflow.
- **83 PostGIS integration tests are written but unrun**, including 12 new dashboard tests for anonymous read-only access, metre-based buffers, overlapping geometry, spatial area membership, cross-boundary coverage, filters, zero versus missing data, and database-error privacy.
- PostgreSQL/PostGIS and native GIS setup, real migration/seed/import, spatial accuracy tests, population/priority methodology and representative-data performance checks are still required. No project database data was changed during this stage.

Frontend checks from `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

Backend helper checks from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s helper_tests -v
```

Only after native setup, initial migration files and Step 3's separate disposable PostGIS test database:

```powershell
..\.venv\Scripts\python.exe manage.py test greenspaces --keepdb
```

### Isolated UI-test fixture

Follow the separate server instructions in [Stage 5](STEP-5.md). Port 5175 must show **UI TEST — SYNTHETIC DATA**. Its dashboard has explicitly TEST-labelled areas/categories and illustrative measurements. **TEST empty category** returns a valid zero; **TEST service failure** returns a deliberate 503; **TEST delayed response** allows cancellation checks. **TEST community garden** illustrates point-only data.

These are browser-state fixtures, not accurate spatial calculations, real Petaling measurements or data to import. They never replace Django in the normal port-5173 preview. Stop the test servers after checking.

## Changed-file guide

```text
backend/
  config/urls.py                         Public dashboard route
  greenspaces/dashboard_queries.py     Filter validation and metric contract
  greenspaces/dashboard_views.py       Read-only PostGIS aggregate query
  greenspaces/test_dashboard.py         Integration tests (unrun)
  helper_tests/test_dashboard_queries.py
frontend/
  src/DashboardPage.jsx                 Filters, indicators and request lifecycle
  src/dashboardApi.js                  Strict response validation
  src/components/DashboardCharts.jsx   Chart.js bar/doughnut and text alternatives
  src/App.jsx                          Dashboard navigation/lazy loading
  src/AccessibilityPage.jsx            Open dashboard link
  tests/dashboardApi.test.js
```

Stage 8 is ready for interface review, not complete end-to-end acceptance. The next stage is reporting; it has not been implemented in this stage.
