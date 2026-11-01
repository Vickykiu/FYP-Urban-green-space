"""Small JSON helpers built on Django; no extra REST framework is required."""
import json
import logging
import math
from functools import wraps

from django.core.exceptions import RequestDataTooBig, ValidationError
from django.db import DatabaseError, IntegrityError
from django.http import JsonResponse
from django.views.csrf import csrf_failure as default_csrf_failure

logger = logging.getLogger(__name__)


def error(message, status, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def staff_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                user = request.user
                if not user.is_authenticated:
                    return error("Administrator login is required.", 401)
                if not user.is_active or not user.is_staff or not user.has_perm(permission):
                    return error("You do not have permission for this action.", 403)
                response = view(request, *args, **kwargs)
                response["Cache-Control"] = "no-store"
                return response
            except ValidationError as exc:
                details = exc.message_dict if hasattr(exc, "message_dict") else {"__all__": exc.messages}
                return error("Record validation failed.", 400, fields=details)
            except IntegrityError:
                return error("The record conflicts with related data. Refresh and try again.", 409)
            except DatabaseError:
                logger.exception("Administrator database request failed")
                return error("The database is unavailable. Check the local database setup.", 503)
        return wrapped
    return decorator


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


def read_record_json(request, allowed_fields):
    if request.content_type != "application/json":
        return None, error("Send the record as application/json.", 415)
    try:
        payload = json.loads(request.body, parse_constant=_reject_constant)
    except RequestDataTooBig:
        return None, error("The request is too large.", 413)
    except (ValueError, UnicodeDecodeError):
        return None, error("Send a valid JSON object.", 400)
    if not isinstance(payload, dict):
        return None, error("Send a JSON object containing record fields.", 400)
    if set(payload) - set(allowed_fields):
        return None, error("The request contains unsupported or read-only fields.", 400)
    for field in ("name", "facilities", "description"):
        if field in payload and not isinstance(payload[field], str):
            return None, error(f"{field} must be text.", 400)
    for field in ("area", "category", "area_size", "latitude", "longitude"):
        if field in payload and (isinstance(payload[field], (bool, list, dict))):
            return None, error(f"{field} must be a numeric value or numeric string.", 400)
        if isinstance(payload.get(field), float) and not math.isfinite(payload[field]):
            return None, error(f"{field} must be a finite number.", 400)
    for field in ("area", "category"):
        if field in payload:
            value = payload[field]
            if not ((type(value) is int and 0 < value <= 2147483647) or
                    (isinstance(value, str) and len(value) <= 10 and value.isascii()
                     and value.isdecimal() and 0 < int(value) <= 2147483647)):
                return None, error(f"{field} must be a positive integer ID.", 400)
    return payload, None


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return error("CSRF verification failed. Refresh your login session and CSRF token.", 403)
    return default_csrf_failure(request, reason=reason)
