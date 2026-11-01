"""Read-only public map endpoints (FR1/FR4), without upload/account metadata."""
import json
import logging
from functools import wraps

from django.contrib.gis.geos import Polygon
from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from config.api import error
from .map_queries import parse_map_query
from .models import AdministrativeArea, GreenSpace, GreenSpaceCategory

logger = logging.getLogger(__name__)
PAGE_SIZE = 200


def public_read(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValueError as exc:
            return error(str(exc), 400)
        except DatabaseError:
            logger.exception("Public map database request failed")
            return error("Map data is unavailable. Please try again later.", 503)
    return wrapped


def green_feature(record, details=False):
    properties = {
        "name": record.name, "area_id": record.area_id, "area_name": record.area.area_name,
        "category_id": record.category_id, "category_name": record.category.category_name,
        "area_size": str(record.area_size) if record.area_size is not None else None,
    }
    if details:
        properties.update({
            "facilities": record.facilities, "description": record.description,
            "latitude": str(record.latitude) if record.latitude is not None else None,
            "longitude": str(record.longitude) if record.longitude is not None else None,
        })
    return {"type": "Feature", "id": record.pk,
            "geometry": json.loads(record.geometry.geojson), "properties": properties}


def clip_to_view(queryset, bbox):
    if bbox is not None:
        boundary = Polygon.from_bbox(bbox)
        boundary.srid = 4326
        queryset = queryset.filter(geometry__intersects=boundary)
    return queryset


def collection(queryset, page_number, serialize):
    paginator = Paginator(queryset, PAGE_SIZE)
    try:
        page = paginator.page(page_number)
        features, has_next = [serialize(item) for item in page.object_list], page.has_next()
    except EmptyPage:
        features, has_next = [], False
    return JsonResponse({"type": "FeatureCollection", "features": features,
                         "count": paginator.count, "page": page_number, "page_size": PAGE_SIZE,
                         "has_next": has_next})


@require_GET
@public_read
def green_spaces(request):
    params = parse_map_query(request.GET)
    records = clip_to_view(GreenSpace.objects.select_related("area", "category").all(), params.bbox)
    if params.category is not None:
        records = records.filter(category_id=params.category)
    if params.search:
        records = records.filter(name__icontains=params.search)
    return collection(records, params.page, green_feature)


@require_GET
@public_read
def green_space_detail(request, record_id):
    record = GreenSpace.objects.select_related("area", "category").filter(pk=record_id).first()
    if record is None:
        return error("This green-space record is no longer available.", 404)
    return JsonResponse(green_feature(record, details=True))


@require_GET
@public_read
def administrative_areas(request):
    params = parse_map_query(request.GET, allow_search=False)
    records = clip_to_view(AdministrativeArea.objects.all(), params.bbox)
    return collection(records, params.page, lambda area: {
        "type": "Feature", "id": area.pk, "geometry": json.loads(area.geometry.geojson),
        "properties": {"area_name": area.area_name, "area_type": area.area_type},
    })


@require_GET
@public_read
def map_options(request):
    categories = list(GreenSpaceCategory.objects.annotate(green_space_count=Count("greenspace")).values(
        "category_id", "category_name", "green_space_count",
    ))
    return JsonResponse({"categories": categories,
                         "green_space_count": GreenSpace.objects.count(),
                         "administrative_area_count": AdministrativeArea.objects.count()})
