# Step 2 Create the spatial database tables

This step turns the report's ERD into PostgreSQL/PostGIS tables using Django migrations. It depends on completing the native installation and connection checks in [Step 1](STEP-1.md).

Current status: the model definitions and the commands below are prepared. The latest check still reports missing GeoDjango native libraries and an unset database password. No migrations have been generated or applied, and no application tables have been created by this project.

## Database structure from your report

Figure 4.16 defines seven entities. The Django models preserve their primary-key and foreign-key column names. PostgreSQL table names use lowercase snake_case.

| Report entity | PostgreSQL table | Purpose |
|---|---|---|
| Administrator | administrator | Administrator accounts and hashed passwords |
| Administrative_Area | administrative_area | Area names, types, and boundary geometry |
| Green_Space_Category | green_space_category | Categories and descriptions |
| Dataset_Upload | dataset_upload | Upload ownership, filenames, status, and record counts |
| Validation_Result | validation_result | Dataset validation results and row-level errors |
| Green_Space | green_space | Green-space attributes, coordinates, geometry, and relationships |
| Planning_Report | planning_report | Report ownership, optional area, metadata, status, and file reference |

The main relationships are:

```text
Administrator ------< Dataset_Upload ------< Validation_Result
      |                      |
      |                      +------------< Green_Space >------ Administrative_Area
      |                                          |
      |                                          +------------ Green_Space_Category
      +-------------< Planning_Report >----------------------- Administrative_Area (optional)
```

Each green space must have an administrative area and category. Its dataset reference is optional, allowing records to be added manually later. Django also creates its own authentication, permissions, sessions, admin-log, and migration-history tables; these support the proposed backend and do not add new project modules.

Administrator uses Django's password-hashing and permission system. Its password is stored in the ERD's password_hash column. Never insert a plain-text password through SQL. The custom Administrator model is configured before the first migration, as required by [Django's custom-user guidance](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#substituting-a-custom-user-model).

Both geometry columns use WGS84 (SRID 4326) with spatial indexes. Point coordinates are stored in longitude, latitude order. A stored coordinate in degrees is not a distance in metres. The later accessibility module must use geography calculations or an appropriate projected coordinate system.

Green-space area_size is measured in hectares, following the Area (ha) label in your supplied Figma record form. Example figures and place names in the prototype are not imported as real data.

## 1 Check the prerequisites

Open PowerShell:

```powershell
Set-Location 'C:\Users\User\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an\outputs\petaling-green-gis'
.\.venv\Scripts\python.exe .\scripts\check_setup.py
```

Continue only when every check reports OK. If it prints NEEDED, finish the corresponding installation or local.toml setting in Step 1 first. You do not need to send any password through chat.

## 2 Generate the migrations

From the same project folder:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py makemigrations accounts greenspaces
```

Expected result: Django creates the first migration files under backend/accounts/migrations and backend/greenspaces/migrations. This generates the database instructions; it does not yet create the tables.

Review the migration plan:

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py migrate --plan
```

For a fresh project, the plan should create the ERD tables plus Django's supporting tables. Keep the generated migration files with your source code. Do not manually create the same tables in pgAdmin: Django should manage their structure.

## 3 Create the tables

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py migrate
```

Expected result: each migration ends with OK. The PostGIS extension should already have been enabled by the postgres administrator in Step 1; the application user does not need to become a database superuser.

This is the command that changes the database. It creates schema objects, not park records or an administrator login. Do not use --fake or delete an existing database to work around migration errors.

## 4 Verify the result

```powershell
.\.venv\Scripts\python.exe .\backend\manage.py showmigrations accounts greenspaces
.\.venv\Scripts\python.exe .\backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe .\backend\manage.py check --database default
.\.venv\Scripts\python.exe .\scripts\verify_database.py
```

Expected results:

- The initial migrations are marked [X].
- No changes are detected between the models and migration files.
- Django reports no system-check errors.
- The verifier finds all seven tables and their ERD columns, plus SRID 4326 and a spatial index on each geometry column.

The verifier uses a read-only database transaction and does not print credentials or account records. These checks establish the schema foundation; data validation, spatial-query accuracy, and performance still need their own later tests.

## Stop at this checkpoint

Step 2 is complete when the tables exist and all four verification commands succeed. Administrator-account setup and record-management functions follow in the next stage. Keep the frontend unchanged for now. The custom interface will follow the supplied Figma reference.

For the migration command meanings, see [Django's migration documentation](https://docs.djangoproject.com/en/5.2/topics/migrations/).
