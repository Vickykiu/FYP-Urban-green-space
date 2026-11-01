# Petaling reference seed

The Petaling feature is extracted without coordinate changes from DOSM's simplified district dataset at commit `21a78e98efd4cd9b022a27a1bf67d167076b7591`, retrieved 22 September 2026. Longitude/latitude coordinates use WGS84. The snapshot is for a district-level planning reference, not cadastral or current legal-boundary certification.

Source and provenance are embedded in `petaling-district.json`. Redistribution terms are retained in `DOSM-LICENSE.md`. This project is not endorsed by DOSM.

The frontend can display this locally bundled boundary when the API fails. It retains the loading-error dialog, labels the map attribution **local seed**, and shows unavailable category counts as dashes. It never substitutes sample parks or reports a successful database connection.

After the Step 1 prerequisites and Step 2 schema migrations, run from the project folder:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py seed_petaling
```

This explicit, transactional seed command creates only the district reference and the four category labels from the prototype. It preserves existing rows and prints the actual IDs for subsequent CSV uploads. It is safe to repeat; ambiguous duplicate names cause a rollback. It is not a schema migration and has not been run on this computer because PostgreSQL/PostGIS and native GIS libraries are not installed.

Real green spaces must still be supplied through the administrator's CSV upload → validation → confirmed import workflow. No names, locations, sizes, opening hours, or counts from the illustrative prototype are inserted as real data.
