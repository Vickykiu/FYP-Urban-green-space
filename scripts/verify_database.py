"""Read-only verification of the initial report-based PostgreSQL/PostGIS schema."""
import sys
import tomllib
from pathlib import Path


REQUIRED_COLUMNS = {
    "administrator": {"admin_id", "username", "email", "password_hash"},
    "administrative_area": {"area_id", "area_name", "area_type", "geometry"},
    "green_space_category": {"category_id", "category_name", "description"},
    "dataset_upload": {
        "dataset_id", "admin_id", "file_name", "uploaded_at", "status",
        "total_records", "valid_records", "invalid_records",
    },
    "validation_result": {
        "validation_id", "dataset_id", "row_number", "field_name",
        "error_message", "severity", "validation_status",
    },
    "green_space": {
        "green_space_id", "area_id", "category_id", "dataset_id", "name",
        "area_size", "facilities", "description", "latitude", "longitude", "geometry",
    },
    "planning_report": {
        "report_id", "admin_id", "area_id", "title", "report_type",
        "reporting_period", "status", "generated_at", "file_path",
    },
}


def check_schema(cursor):
    failures = []
    cursor.execute("SELECT PostGIS_Version()")
    print(f"OK: PostGIS {cursor.fetchone()[0]}")
    for table, expected_columns in REQUIRED_COLUMNS.items():
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            (table,),
        )
        actual_columns = {row[0] for row in cursor.fetchall()}
        missing = expected_columns - actual_columns
        if missing:
            failures.append(f"{table}: missing columns or table ({', '.join(sorted(missing))}).")
        else:
            print(f"OK: {table} contains the ERD columns.")

    for table in ("administrative_area", "green_space"):
        cursor.execute(
            "SELECT srid FROM geometry_columns "
            "WHERE f_table_schema = current_schema() AND f_table_name = %s "
            "AND f_geometry_column = 'geometry'",
            (table,),
        )
        result = cursor.fetchone()
        if result is None or result[0] != 4326:
            failures.append(f"{table}.geometry must use SRID 4326.")
        else:
            print(f"OK: {table}.geometry uses WGS84 (4326).")
        cursor.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = current_schema() AND tablename = %s",
            (table,),
        )
        if not any("using gist" in row[0].lower() and "geometry" in row[0].lower() for row in cursor.fetchall()):
            failures.append(f"{table}: expected a geometry GiST spatial index.")
        else:
            print(f"OK: {table} has a spatial index.")

    for failure in failures:
        print(f"NEEDED: {failure}")
    return not failures


def main():
    config_file = Path(__file__).resolve().parent.parent / "backend" / "local.toml"
    if not config_file.is_file():
        print("NEEDED: Complete STEP-1.md and configure backend/local.toml first.")
        return 1
    try:
        with config_file.open("rb") as source:
            database = tomllib.load(source)["database"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        print("NEEDED: Correct the database section in backend/local.toml.")
        return 1
    if not database.get("password"):
        print("NEEDED: Configure the petaling_app password in backend/local.toml.")
        print("Database verification was not run. No tables or records were changed.")
        return 1
    try:
        import psycopg
        with psycopg.connect(
            dbname=database.get("name", "petaling_green_gis"),
            user=database.get("user", "petaling_app"), password=database["password"],
            host=database.get("host", "127.0.0.1"), port=database.get("port", 5432),
            connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                success = check_schema(cursor)
    except Exception as error:
        print(f"NEEDED: Database verification could not finish ({type(error).__name__}).")
        print("Check PostgreSQL, PostGIS, credentials, and migration output. No records were changed.")
        return 1
    if not success:
        return 1
    print("Initial schema checks passed. No records were inserted or modified.")
    print("This verifies table columns, geometry SRIDs, and spatial indexes; it is not full system testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
