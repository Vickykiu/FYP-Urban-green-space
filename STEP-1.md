# Step 1 Development environment setup

The goal is to start React, configure Django/GeoDjango, and verify a real PostgreSQL/PostGIS connection. Finish this before database migrations, dataset import, or interface development.

## Current progress

Checked on 20 September 2026:

- Python 3.11.3, Node.js 24.12.0, Git 2.53.0, and Visual Studio Code are available.
- This project's .venv contains Django 5.2.17 and Psycopg 3.3.6. Their dependency check passed.
- backend/local.toml has been created with a private random Django secret. The database password and GIS paths still need to be filled in.
- The React dependencies are installed. The starter build passed, the development server started, and its page returned HTTP 200.
- PostgreSQL was not detected in the standard installation locations or Windows services. No PostgreSQL database has been created.
- Native GIS libraries were not detected in the standard OSGeo4W or QGIS locations. The backend connection has not passed verification.

If you installed PostgreSQL or GIS libraries in another location, use those paths below instead of installing another copy.

## 1 Open the project

Open PowerShell and run:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis'
code .
```

All remaining commands start from this project folder unless stated otherwise. Keep the report in its original location; it is a reference and is not modified.

## 2 Install PostgreSQL and PostGIS

Use the [official PostgreSQL Windows download page](https://www.postgresql.org/download/windows/). Choose PostgreSQL 17 for Windows x64, using its current maintenance release. This is an implementation version choice; the proposal does not specify a version.

In the installer, include PostgreSQL Server, Command Line Tools, pgAdmin 4, and Stack Builder. Keep port 5432 unless it is already occupied. Choose and keep the postgres administrator password privately.

Open Stack Builder, select the PostgreSQL 17 installation, then install the matching PostGIS package under Spatial Extensions. PostgreSQL is the database server; PostGIS adds the spatial functions. pgAdmin and Stack Builder come with the Windows installer and are supporting utilities.

Source: [PostgreSQL Windows installer components](https://www.postgresql.org/download/windows/) and [GeoDjango Windows installation](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/#windows).

## 3 Create the project database

Open SQL Shell (psql) from the Start menu. Use localhost, database postgres, port 5432, and username postgres. Enter the password you chose during installation.

Run these SQL Shell commands once:

```sql
CREATE ROLE petaling_app LOGIN;
\password petaling_app
CREATE DATABASE petaling_green_gis OWNER petaling_app;
\connect petaling_green_gis
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Full_Version();
```

The password command asks for a new password twice without putting it into SQL history. Save it privately; Django will use this petaling_app password. If the role or database already exists, inspect it and reuse it rather than deleting or recreating it. The application role does not need superuser privileges.

Expected result: the final query prints a PostGIS version. This creates the database container only; application tables come in the next stage.

## 4 Install the GIS libraries

GeoDjango needs GDAL, GEOS, and PROJ on the computer running Python, in addition to the PostGIS extension inside PostgreSQL. These are runtime dependencies of the proposed stack.

Use [OSGeo4W](https://trac.osgeo.org/osgeo4w/), as described in the [GeoDjango Windows instructions](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/#windows). Install its 64-bit GDAL package and required dependencies; a common root is C:\OSGeo4W. If its installer offers an Express Web-GIS option, choose GDAL there; otherwise select GDAL using Advanced Install. Do not install a separate Python GDAL package through pip for this setup.

After installation, find the actual DLL names in PowerShell:

```powershell
Get-ChildItem 'C:\OSGeo4W\bin\gdal*.dll'
Get-ChildItem 'C:\OSGeo4W\bin\geos_c.dll'
Get-ChildItem 'C:\OSGeo4W\apps\gdal\share\gdal'
Get-ChildItem 'C:\OSGeo4W\share\proj\proj.db'
```

Paths may differ by installation. Use the main GDAL DLL, not a plugin or helper DLL. QGIS remains your proposed data-preparation tool for later stages; it is not necessary to launch QGIS for this connection check.

## 5 Prepare Python and local settings

From the project folder:

On this computer, the virtual environment, packages, and local settings file have already been prepared. Open backend/local.toml and complete its values. The following commands are for repeating setup on a fresh copy; do not recreate an existing environment.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe .\scripts\init_local.py
code .\backend\local.toml
```

Using the virtual environment's Python directly avoids changing PowerShell's execution policy. Skip the first command if this project's .venv already exists.

The settings initializer creates a random Django secret and never overwrites an existing local.toml. Leave the secret private. Fill in the database password and GIS paths. For example, the GIS section might look like this after replacing the GDAL filename with the actual one you found:

```toml
[gis]
dll_directories = ["C:/OSGeo4W/bin"]
gdal_library_path = "C:/OSGeo4W/bin/REPLACE_WITH_ACTUAL_GDAL_FILENAME.dll"
geos_library_path = "C:/OSGeo4W/bin/geos_c.dll"
gdal_data = "C:/OSGeo4W/apps/gdal/share/gdal"
proj_data = "C:/OSGeo4W/share/proj"
```

Use forward slashes in TOML paths. Set password in the existing [database] section to the petaling_app password. If the password contains backslashes, use a TOML literal string with single quotes, provided the password itself contains no single quote. Never paste passwords into chat. The local.toml file and .venv are excluded from Git.

Check the environment:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_setup.py
```

Expected result: Python, Django, Psycopg, GIS libraries, PostgreSQL/PostGIS, and Django configuration all report OK. A NEEDED message means that prerequisite is still missing. This checker performs no migrations and changes no database records.

Then start the backend:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py runserver 127.0.0.1:8000
```

An unapplied-migrations warning is expected at this stage. Do not run migrations yet. The health endpoint only checks the database and PostGIS, so it does not require application tables.

In a second PowerShell window, verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
```

Expected result: status ok, database ok, and a PostGIS version. A 503 response means the database or extension check failed; check the backend console, local settings, and PostgreSQL service. Do not use the administrator page until migrations and account setup in the next stage.

## 6 Start the React environment

Open another PowerShell window:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis\frontend'
npm.cmd ci
npm.cmd run dev
```

Open [the local React app](http://127.0.0.1:5173/) and choose Check connection. It should report that React, Django, and PostGIS are connected. This is a temporary setup screen. The later interface will follow [your Figma design](https://www.figma.com/design/WvnlAkodH423nIUpDd5mv0/Untitled?node-id=0-1).

Vite runs and builds the React frontend; it is not an alternative backend. The native configuration loader is used because the default loader hit a Windows process-permission error in this environment. Leaflet and Chart.js are installed for later modules.

You can verify the frontend build with:

```powershell
npm.cmd run build
```

## Completion checkpoint

Step 1 is complete only when the setup checker passes, the health endpoint reports a real PostGIS connection, and the React connection check succeeds. Stop here for this stage. Database migrations, administrator accounts, CSV functions, data import, spatial analysis, and the Figma interface belong to later stages.

The latest check passed Python, Django, and Psycopg, then reported the missing GIS libraries and database credentials. Python source compilation also passed. Database connectivity and the complete React-to-PostGIS check remain unverified until the native prerequisites are installed.
