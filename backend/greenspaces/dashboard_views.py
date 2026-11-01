"""Read-only district dashboard. Coverage is LAND, never population coverage."""
import json
import logging
from django.db import DatabaseError, connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from config.api import error
from .dashboard_queries import dashboard_metrics, parse_dashboard
from .nearby_views import study_area

logger = logging.getLogger(__name__)

# Fixed 1 km threshold matches the dashboard prototype. Spatial intersections
# define membership; no hierarchy or mutually exclusive planning wards is assumed.
DASHBOARD_SQL = """
WITH input AS (
    SELECT ST_GeomFromEWKT(%s) AS district, %s::integer AS area_id, %s::integer AS category_id,
           %s::boolean AS include_inventory
), district_parks AS MATERIALIZED (
    SELECT g.* FROM green_space g, input i WHERE ST_Intersects(g.geometry, i.district)
), parks AS MATERIALIZED (
    SELECT p.* FROM district_parks p, input i WHERE i.category_id IS NULL OR p.category_id = i.category_id
), clipped_zones AS (
    SELECT a.area_id, a.area_name, a.area_type,
           ST_CollectionExtract(ST_Intersection(a.geometry, i.district), 3) AS geom
    FROM administrative_area a, input i WHERE ST_Intersects(a.geometry, i.district)
), zones AS MATERIALIZED (
    SELECT * FROM clipped_zones WHERE NOT ST_IsEmpty(geom) AND ST_Area(geom::geography) > 0
), selected_zone AS (
    SELECT 0 AS area_id, 'Petaling District' AS area_name, 'District' AS area_type, district AS geom
    FROM input WHERE area_id IS NULL
    UNION ALL SELECT z.* FROM zones z, input i WHERE z.area_id = i.area_id
), targets AS (
    SELECT z.* FROM zones z, input i WHERE i.area_id IS NULL OR z.area_id = i.area_id
    UNION ALL SELECT * FROM selected_zone WHERE area_id = 0
), catchment AS MATERIALIZED (
    SELECT ST_Union(ST_Buffer(geometry::geography, 1000, 64)::geometry) AS geom FROM parks
), stats AS (
    SELECT z.area_id, z.area_name, z.area_type, ST_Area(z.geom::geography) AS zone_area_m2,
           CASE WHEN c.geom IS NULL THEN 0 ELSE ST_Area(
               ST_CollectionExtract(ST_Intersection(c.geom, z.geom), 3)::geography) END AS covered_land_m2,
           p.space_count, p.point_count, p.green_area_m2
    FROM targets z CROSS JOIN catchment c CROSS JOIN LATERAL (
        SELECT COUNT(*)::integer AS space_count,
               COUNT(*) FILTER (WHERE GeometryType(geometry) = 'POINT')::integer AS point_count,
               COALESCE(ST_Area((ST_Union(ST_CollectionExtract(ST_Intersection(geometry, z.geom), 3))
                   FILTER (WHERE GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')))::geography), 0) AS green_area_m2
        FROM parks WHERE ST_Intersects(geometry, z.geom)
    ) p
), categories AS (
    SELECT c.category_id, c.category_name, COUNT(p.green_space_id)::integer AS space_count
    FROM green_space_category c CROSS JOIN selected_zone z CROSS JOIN input i
    LEFT JOIN parks p ON p.category_id = c.category_id AND ST_Intersects(p.geometry, z.geom)
    WHERE i.category_id IS NULL OR c.category_id = i.category_id
    GROUP BY c.category_id, c.category_name
)
SELECT jsonb_build_object(
    'available', (SELECT COUNT(*) FROM district_parks),
    'areas', COALESCE((SELECT jsonb_agg(jsonb_build_object('area_id', area_id, 'area_name', area_name,
        'area_type', area_type) ORDER BY area_name, area_id) FROM zones), '[]'::jsonb),
    'category_options', COALESCE((SELECT jsonb_agg(jsonb_build_object('category_id', category_id,
        'category_name', category_name) ORDER BY category_name, category_id) FROM green_space_category), '[]'::jsonb),
    'rows', COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY area_name, area_id) FROM stats s), '[]'::jsonb),
    'categories', COALESCE((SELECT jsonb_agg(to_jsonb(c) ORDER BY category_name, category_id) FROM categories c), '[]'::jsonb),
    'inventory', COALESCE((SELECT jsonb_agg(to_jsonb(g) ORDER BY name, green_space_id) FROM (
        SELECT p.green_space_id, p.name, c.category_name, p.area_size::text AS recorded_area_ha,
               GeometryType(p.geometry) AS geometry_type
        FROM parks p JOIN green_space_category c USING (category_id)
        CROSS JOIN selected_zone z CROSS JOIN input i
        WHERE i.include_inventory AND ST_Intersects(p.geometry, z.geom)
        ORDER BY p.name, p.green_space_id LIMIT 1001
    ) g), '[]'::jsonb)
)
"""


class DashboardUnavailable(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def dashboard_data(filters, include_inventory=False):
    """Shared snapshot query for the dashboard and persisted reports."""
    area = study_area()
    if area is None:
        raise DashboardUnavailable('Configure one Petaling district boundary first.', 'study_area_unavailable')
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '5000ms'")
        cursor.execute(DASHBOARD_SQL, [area.geometry.ewkt, filters['area'], filters['category'], include_inventory])
        data = cursor.fetchone()[0]
    data = json.loads(data) if isinstance(data, str) else data
    if ((filters['area'] is not None and not any(a['area_id'] == filters['area'] for a in data['areas']))
            or (filters['category'] is not None and not any(c['category_id'] == filters['category'] for c in data['category_options']))):
        raise ValueError('Select an available administrative area and category.')
    if data['available'] == 0:
        raise DashboardUnavailable('Import approved green-space data before viewing the dashboard.', 'green_space_data_unavailable')
    selected = next(r for r in data['rows'] if r['area_id'] == (filters['area'] or 0))
    result = {
        'filters': filters, 'radius_m': 1000, 'coverage_basis': 'land_area_within_park_buffers',
        'options': {'areas': data['areas'], 'categories': data['category_options']},
        'summary': dashboard_metrics(selected),
        'areas': [{**{k: r[k] for k in ('area_id', 'area_name', 'area_type')}, **dashboard_metrics(r)}
                  for r in data['rows'] if r['area_id'] != 0],
        'categories': data['categories'], 'priority_areas': [], 'priority_status': 'unavailable',
    }
    if include_inventory:
        result['inventory'] = data['inventory']
    return result


@require_GET
def dashboard(request):
    try:
        response = JsonResponse(dashboard_data(parse_dashboard(request.GET)))
    except DashboardUnavailable as exc:
        response = error(str(exc), 503, code=exc.code)
    except ValueError as exc:
        response = error(str(exc), 400, code='invalid_query')
    except DatabaseError:
        logger.warning('Public planning dashboard database unavailable')
        response = error('Dashboard information cannot be displayed. Please retry.', 503, code='database_unavailable')
    response['Cache-Control'] = 'no-store'
    return response
