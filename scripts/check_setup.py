"""Read-only Step 1 checks; no database creation, migrations, or data changes."""
import importlib
import os
import sys
from pathlib import Path


def main():
    print("Petaling GIS - Step 1 environment check")
    if sys.version_info < (3, 11):
        print("NEEDED: Python 3.11 or later.")
        return 1
    print(f"OK: Python {sys.version.split()[0]}")
    missing = False
    for module_name in ("django", "psycopg"):
        try:
            module = importlib.import_module(module_name)
            version = module.get_version() if module_name == "django" else module.__version__
            print(f"OK: {module_name} {version}")
        except ImportError:
            missing = True
            print(f"NEEDED: {module_name}. Install backend/requirements.txt in your virtual environment.")
    if missing:
        return 1

    backend = Path(__file__).resolve().parent.parent / "backend"
    if not (backend / "local.toml").is_file():
        print("NEEDED: Run python scripts/init_local.py, then fill in backend/local.toml.")
        return 1
    sys.path.insert(0, str(backend))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.conf import settings
        settings.DATABASES  # Load process-local DLL paths before importing GIS.
    except Exception as error:
        print(f"NEEDED: Correct backend/local.toml ({type(error).__name__}).")
        return 1
    gis_ready = True
    try:
        from django.contrib.gis.geos import Point
        point = Point(101.6067, 3.1073, srid=4326)
        point.transform(3857)
        print("OK: GEOS, GDAL and coordinate transformation are available.")
    except Exception as error:
        gis_ready = False
        print(f"NEEDED: GeoDjango native libraries or their configured paths ({type(error).__name__}).")
        print("        Follow the GIS libraries section in STEP-1.md.")

    db = settings.DATABASES["default"]
    database_ready = True
    if not db["PASSWORD"]:
        database_ready = False
        print("NEEDED: Set your petaling_app database password in backend/local.toml.")
    else:
        try:
            import psycopg
            with psycopg.connect(
                dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"],
                host=db["HOST"], port=db["PORT"], connect_timeout=5,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT PostGIS_Version()")
                    print(f"OK: PostgreSQL connected; PostGIS {cursor.fetchone()[0]}")
        except Exception as error:
            database_ready = False
            print(f"NEEDED: PostgreSQL/PostGIS connection ({type(error).__name__}).")
            print("        Check the service, database, extension, and local credentials.")
    if not (gis_ready and database_ready):
        print("Step 1 is not complete yet. No database data was changed.")
        return 1
    try:
        import django
        django.setup()
        from django.core.checks import run_checks
        errors = [issue for issue in run_checks() if issue.level >= 40]
        if errors:
            for issue in errors:
                print(f"NEEDED: Django check {issue.id}: {issue.msg}")
            return 1
    except Exception as error:
        print(f"NEEDED: Django configuration ({type(error).__name__}).")
        return 1
    print("OK: Django configuration checks passed.")
    print("Step 1 backend connection is ready. No application tables were created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
