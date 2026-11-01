"""Local development settings for the proposed React / GeoDjango / PostGIS stack."""
import os
import tomllib
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_FILE = BASE_DIR / "local.toml"
if not LOCAL_FILE.is_file():
    raise ImproperlyConfigured("Run: python scripts/init_local.py from the project folder.")
with LOCAL_FILE.open("rb") as config_file:
    local = tomllib.load(config_file)

SECRET_KEY = local["django"]["secret_key"]
DEBUG = local["django"].get("debug", True)
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]

# Windows DLL discovery is scoped to this Python process, not the system PATH.
gis = local.get("gis", {})
_dll_handles = []
if os.name == "nt":
    for folder in gis.get("dll_directories", []):
        directory = Path(folder)
        if not directory.is_dir():
            raise ImproperlyConfigured(f"GIS library directory does not exist: {directory}")
        _dll_handles.append(os.add_dll_directory(str(directory)))
        os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
for config_key, env_key in (("gdal_data", "GDAL_DATA"), ("proj_data", "PROJ_DATA")):
    if gis.get(config_key):
        os.environ[env_key] = gis[config_key]
if gis.get("gdal_library_path"):
    GDAL_LIBRARY_PATH = gis["gdal_library_path"]
if gis.get("geos_library_path"):
    GEOS_LIBRARY_PATH = gis["geos_library_path"]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "django.contrib.gis", "accounts", "greenspaces",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
db = local["database"]
DATABASES = {"default": {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": db.get("name", "petaling_green_gis"),
    "USER": db.get("user", "petaling_app"),
    "PASSWORD": db.get("password", ""),
    "HOST": db.get("host", "127.0.0.1"),
    "PORT": db.get("port", 5432),
    "OPTIONS": {"connect_timeout": 5},
}}
AUTH_USER_MODEL = "accounts.Administrator"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_HANDLERS = [
    "greenspaces.upload_limits.CsvSizeLimitUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "config.api.csrf_failure"
# Local Vite proxy requests carry the frontend Origin header.
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
