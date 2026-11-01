# Petaling Green Space GIS

Start with [STEP-1.md](STEP-1.md). This stage prepares the development environment and checks the connection between React, Django/GeoDjango, and PostgreSQL/PostGIS.

Once those checks pass, follow [STEP-2.md](STEP-2.md) to generate and apply the report-based database schema and verify its tables. Step 2 is prepared but has not been run because the local database and GIS setup is still incomplete.

Continue with [STEP-3.md](STEP-3.md) for administrator-account setup and green-space record management. The backend code and tests are prepared; the database-independent helper tests pass, but PostGIS integration tests remain blocked by Step 1's missing prerequisites. No account or green-space data has been created.

Next, [STEP-4.md](STEP-4.md) covers CSV upload, validation, and explicit all-or-nothing import, based on FR8/FR9. The backend code is prepared, with 28 helper tests passing across the project. The 31 PostGIS integration tests are written but remain unrun. No project datasets have been uploaded or imported.

The interface includes [Stage 5's interactive map](STEP-5.md), [Stage 6's location selection and nearby search](STEP-6.md), [Stage 7's distance-based accessibility coverage](STEP-7.md), and [Stage 8's planning dashboard](STEP-8.md), following the prototype's labels, icon symbols, cards and dialogs. Public users can explore these pages without an account. Park records remain administrator CSV data, with no OpenStreetMap tiles or imports. A sourced Petaling district snapshot and repeatable reference seed command are prepared. The latest checks passed 56 backend helper tests, 44 frontend tests and the production build; 83 PostGIS integration tests remain unrun. Browser checks used clearly labelled synthetic data, not a working project database. No database records were added.

The project follows FYP.docx, particularly Sections 2.5.3, 3.4, and 4.3, plus the ERD in Figure 4.16. The interface reference for subsequent stages is the [supplied Figma design](https://www.figma.com/design/WvnlAkodH423nIUpDd5mv0/Untitled?node-id=0-1).

```text
petaling-green-gis/
  backend/                 Django project and draft report-based models
    config/                Settings, URLs, health endpoint, and API helpers
    accounts/              Administrator model
    greenspaces/           ERD models, record APIs, CSV validation/import, tests
    helper_tests/          Tests that do not require the database
    manage.py
    requirements.txt
  frontend/                React + Leaflet maps, Chart.js dashboard and tests
  database/                PostGIS extension setup SQL
  data/                    DOSM Petaling boundary snapshot, provenance and licence
  scripts/                 Local configuration and prerequisite checks
  STEP-1.md                Windows setup commands and completion checks
  STEP-2.md                ERD mapping, migration commands, and schema checks
  STEP-3.md                Administrator setup, record management, and tests
  STEP-4.md                CSV format, upload/validation/import, and tests
  STEP-5.md                Public map, Figma-based layout, endpoints, and tests
  STEP-6.md                Location selection, nearby search, scope and checks
  STEP-7.md                Accessibility coverage, metric definitions and checks
  STEP-8.md                Planning dashboard, area/category filters and checks
```

The React interface implements the interactive map, nearby/location, accessibility and planning dashboard screens; other pages retain their original labels but remain disabled. The user confirmed PostgreSQL/PostGIS and QGIS are not installed. Models have not been migrated or validated against a running spatial database. Steps 3-8 contain code but are not verified end to end with PostGIS. General street-address lookup remains pending: the report names no address dataset/service, so only uploaded place-name lookup, map points, explicit coordinates and user-invoked device location are implemented. Population coverage, historical changes and priority-gap indicators remain unavailable because their data/methods are not configured. Dashboard coverage is explicitly land within 1 km of uploaded parks, not population coverage. Mapped park-polygon area is measured separately; point records never receive invented footprints. Reporting and the custom administrator frontend remain for later stages. When Django is unavailable, the normal app reports the connection problem; map pages can display an attributed local district boundary, never fake parks or a successful database state. The SVG icons are recreated from the reference, not exported Figma source assets.

React, Leaflet, Chart.js, Django, GeoDjango, PostgreSQL, and PostGIS are the selected application stack. Python, Node.js/npm, Vite, Psycopg, and native GIS libraries support that stack. Docker is not used.

The application is configured for local development on 127.0.0.1. Publishing and production configuration are outside these foundation steps.
