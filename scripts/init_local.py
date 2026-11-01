"""Create ignored local settings once. Never print or overwrite existing secrets."""
import secrets
from pathlib import Path

project = Path(__file__).resolve().parent.parent
target = project / "backend" / "local.toml"
template = '''# Local development settings. Do not commit this file.
[django]
secret_key = "{secret}"
debug = true

[database]
name = "petaling_green_gis"
user = "petaling_app"
password = ""
host = "127.0.0.1"
port = 5432

# Fill these paths after installing the GeoDjango native libraries.
# Use forward slashes, for example C:/OSGeo4W/bin.
[gis]
dll_directories = []
gdal_library_path = ""
geos_library_path = ""
gdal_data = ""
proj_data = ""
'''
try:
    with target.open("x", encoding="utf-8") as output:
        output.write(template.format(secret=secrets.token_urlsafe(64)))
except FileExistsError:
    print("backend/local.toml already exists; no changes made.")
else:
    print("Created backend/local.toml. Fill in your database password and GIS library paths.")

