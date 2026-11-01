"""FR5: parameterized, read-only PostGIS coverage analysis; no persisted origins.

Geography buffering is an approximation in a locally selected projected CRS.
Exact geography distance determines park reach, consistent with nearby search.
Mapped polygon area is clipped to the district catchment and dissolved before
measurement. Point records never contribute invented footprint areas.
"""
import json
from django.contrib.gis.geos import Point
from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from config.api import error
from .coverage_queries import coverage_metrics, parse_coverage
from .nearby_views import payload, private_response, study_area

DISPLAY_LIMIT = 2000

# One statement keeps counts, bands and displayed records on one DB snapshot.
# All user values are bound parameters; identifiers are the report model tables.
ANALYSIS_SQL = """
WITH input AS (
    SELECT ST_SetSRID(ST_Point(%s, %s), 4326) AS origin,
           ST_GeomFromEWKT(%s) AS district
), district_parks AS MATERIALIZED (
    SELECT g.*, c.category_name, a.area_name,
           ST_Distance(g.geometry::geography, i.origin::geography) AS distance_m
    FROM green_space g
    JOIN green_space_category c USING (category_id)
    JOIN administrative_area a USING (area_id)
    CROSS JOIN input i
    WHERE ST_Intersects(g.geometry, i.district)
), zones AS (
    SELECT radius_m, ST_CollectionExtract(ST_Intersection(
        ST_Buffer(i.origin::geography, radius_m, 64)::geometry, i.district), 3) AS geom
    FROM input i CROSS JOIN unnest(%s::integer[]) AS distances(radius_m)
), band_metrics AS (
    SELECT z.radius_m, ST_AsGeoJSON(z.geom, 9)::jsonb AS geometry,
           ST_Area(z.geom::geography) AS coverage_area_m2,
           COUNT(p.green_space_id)::integer AS green_space_count,
           COUNT(p.green_space_id) FILTER (WHERE GeometryType(p.geometry) = 'POINT')::integer AS point_count,
           COUNT(p.green_space_id) FILTER (WHERE GeometryType(p.geometry) IN ('POLYGON', 'MULTIPOLYGON'))::integer AS polygon_count,
           COALESCE(ST_Area((ST_Union(ST_CollectionExtract(ST_Intersection(p.geometry, z.geom), 3))
               FILTER (WHERE GeometryType(p.geometry) IN ('POLYGON', 'MULTIPOLYGON')))::geography), 0) AS green_area_m2
    FROM zones z LEFT JOIN district_parks p ON p.distance_m <= z.radius_m
    GROUP BY z.radius_m, z.geom
), displayed AS (
    SELECT * FROM district_parks WHERE distance_m <= %s
    ORDER BY distance_m, green_space_id LIMIT %s
)
SELECT (SELECT COUNT(*) FROM district_parks),
       (SELECT jsonb_agg(to_jsonb(b) ORDER BY radius_m) FROM band_metrics b),
       COALESCE((SELECT jsonb_agg(jsonb_build_object(
           'type', 'Feature', 'id', green_space_id,
           'geometry', ST_AsGeoJSON(geometry, 9)::jsonb,
           'properties', jsonb_build_object('name', name, 'category_id', category_id,
               'category_name', category_name, 'area_id', area_id, 'area_name', area_name,
               'area_size', area_size::text, 'distance_m', distance_m)
       ) ORDER BY distance_m, green_space_id) FROM displayed), '[]'::jsonb)
"""


@require_POST
@private_response
def analyse(request):
    query = parse_coverage(payload(request))
    area = study_area()
    if area is None:
        return error('Configure one Petaling district boundary before analysis.', 503, code='study_area_unavailable')
    if not area.geometry.covers(Point(query.longitude, query.latitude, srid=4326)):
        return error('Select a location inside Petaling District.', 400, code='outside_study_area')
    radii = sorted({500, 1000, 2000, query.radius_m})
    with transaction.atomic(), connection.cursor() as cursor:
        # Bounds resource use; this is not a claim that the 3-second NFR passes.
        cursor.execute("SET LOCAL statement_timeout = '5000ms'")
        cursor.execute(ANALYSIS_SQL, [query.longitude, query.latitude, area.geometry.ewkt,
                                     radii, query.radius_m, DISPLAY_LIMIT])
        available, bands, features = cursor.fetchone()
    # Django's PostgreSQL adapter deliberately leaves raw jsonb as text.
    bands = json.loads(bands) if isinstance(bands, str) else bands
    features = json.loads(features) if isinstance(features, str) else features
    if available == 0:
        return error('Import approved green-space data before analysis.', 503, code='green_space_data_unavailable')
    metrics = coverage_metrics(bands, query.radius_m)
    return JsonResponse({
        'method': 'distance_buffer', 'radius_m': query.radius_m,
        'coverage': {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'id': band['radius_m'], 'geometry': band['geometry'], 'properties': {
                'radius_m': band['radius_m'], 'selected': band['radius_m'] == query.radius_m,
                'coverage_area_m2': band['coverage_area_m2']}} for band in bands]},
        'metrics': metrics,
        'green_spaces': {'type': 'FeatureCollection', 'features': features,
                         'count': metrics['green_spaces_reached'], 'limited': metrics['green_spaces_reached'] > len(features)},
        'limitations': ['Spatial proximity only; not walking routes, travel time or barrier-aware access.',
                       'Population coverage and priority gaps cannot be assessed without population data.',
                       'Only mapped polygon footprints contribute to accessible green-space area.'],
    })
