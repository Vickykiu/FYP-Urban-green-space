import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    """Verify a real PostGIS connection; never substitute sample success data."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version()")
            version = cursor.fetchone()[0]
    except DatabaseError:
        logger.exception("PostGIS health check failed")
        return JsonResponse({
            "status": "unavailable", "database": "unavailable",
            "message": "Check PostgreSQL, the PostGIS extension, and backend/local.toml.",
        }, status=503)
    return JsonResponse({"status": "ok", "database": "ok", "postgis": version})

