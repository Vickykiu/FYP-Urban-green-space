"""Anonymous read-only searches. POST keeps coordinates out of URL access logs.

Normal Django CSRF protection remains enabled; no account is required.
Distances are spheroidal metres to the nearest point of the stored geometry.
They are not walking distances, entrance distances, or travel-time estimates.
"""
import json
import logging
from functools import wraps

from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import Distance, Intersection, PointOnSurface
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.core.exceptions import RequestDataTooBig
from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST

from config.api import error
from .models import AdministrativeArea, GreenSpace
from .nearby_queries import MAX_RADIUS_M, MIN_RADIUS_M, parse_nearby, parse_place_search
from .public_views import green_feature

logger = logging.getLogger(__name__)
PAGE_SIZE = 200


def private_response(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except (ValueError, UnicodeDecodeError):
            response = error('Check the location and search values.', 400, code='invalid_query')
        except RequestDataTooBig:
            response = error('The search request is too large.', 413, code='invalid_query')
        except DatabaseError:
            # Do not log user coordinates, addresses, request bodies, or SQL parameters.
            logger.warning('Public location search database unavailable')
            response = error('Search data is unavailable. Please try again.', 503, code='database_unavailable')
        response['Cache-Control'] = 'no-store'
        return response
    return wrapped


def payload(request):
    if request.content_type != 'application/json':
        raise ValueError('Use JSON.')
    if len(request.body) > 2048:
        raise ValueError('Search request too large.')
    def reject_constant(value):
        raise ValueError('Non-finite number')
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate field')
            result[key] = value
        return result
    return json.loads(request.body, parse_constant=reject_constant, object_pairs_hook=unique_keys)


def study_area():
    matches = list(AdministrativeArea.objects.filter(area_name__iexact='Petaling', area_type__iexact='District')[:2])
    return matches[0] if len(matches) == 1 else None


@require_GET
@private_response
def options(request):
    return JsonResponse({'csrf_token': get_token(request), 'min_radius_m': MIN_RADIUS_M,
        'max_radius_m': MAX_RADIUS_M, 'radii_m': [500, 1000, 2000],
        'location_lookup': 'administrator_place_names', 'street_address_lookup': False})


@require_POST
@private_response
def nearby(request):
    query = parse_nearby(payload(request))
    origin = Point(query.longitude, query.latitude, srid=4326)
    area = study_area()
    if area is None:
        return error('Configure one Petaling district boundary before searching.', 503, code='study_area_unavailable')
    if not area.geometry.covers(origin):
        return error('Select a starting location inside Petaling District.', 400, code='outside_study_area')
    # Geography casts make both the radius test and distance measurement metres.
    # Existing geometry index helps restrict candidates to the district. A
    # geography-expression index may be added after representative-data profiling.
    records = (GreenSpace.objects.select_related('area', 'category')
        .filter(geometry__intersects=area.geometry)
        .alias(geography=Cast('geometry', GeometryField(srid=4326, geography=True)))
        .filter(geography__dwithin=(origin, D(m=query.radius_m)))
        .annotate(distance=Distance('geography', origin))
        .order_by('distance', 'green_space_id'))
    paginator = Paginator(records, PAGE_SIZE)
    try:
        page = paginator.page(query.page)
        features = []
        for record in page.object_list:
            feature = green_feature(record)
            # Preserve precision for ordering and avoid rounding a just-outside
            # record into a radius. Filtering has already happened in PostGIS.
            feature['properties']['distance_m'] = record.distance.m
            features.append(feature)
        has_next = page.has_next()
    except EmptyPage:
        features, has_next = [], False
    return JsonResponse({'type': 'FeatureCollection', 'features': features, 'count': paginator.count,
        'page': query.page, 'page_size': PAGE_SIZE, 'has_next': has_next,
        'radius_m': query.radius_m, 'distance_method': 'spheroidal_straight_line_to_geometry'})


@require_POST
@private_response
def places(request):
    query = parse_place_search(payload(request))
    area = study_area()
    if area is None:
        return error('Configure the Petaling district boundary first.', 503, code='study_area_unavailable')
    records = (GreenSpace.objects.select_related('area')
        .filter(name__icontains=query, geometry__intersects=area.geometry)
        .annotate(location=PointOnSurface(Intersection('geometry', area.geometry)))
        .order_by('name', 'green_space_id')[:11])
    results = [{'id': record.pk, 'label': f'{record.name}, {record.area.area_name}',
                'latitude': record.location.y, 'longitude': record.location.x, 'source': 'administrator_place'}
               for record in records]
    return JsonResponse({'results': results[:10], 'has_more': len(results) > 10,
                         'street_address_lookup': False})
