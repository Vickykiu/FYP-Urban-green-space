"""Database-independent contracts for FR5; unknown population is never zero."""
from .nearby_queries import parse_nearby


def parse_coverage(payload):
    if not isinstance(payload, dict) or set(payload) != {'latitude', 'longitude', 'radius_m'}:
        raise ValueError('Send latitude, longitude and radius_m only.')
    return parse_nearby(payload)


def coverage_metrics(bands, radius):
    selected = next(band for band in bands if band['radius_m'] == radius)
    baseline = next(band for band in bands if band['radius_m'] == 500)
    missing = selected['point_count']
    measured = selected['polygon_count'] > 0 or selected['green_space_count'] == 0
    area = selected['green_area_m2'] / 10000 if measured else None
    zone = selected['coverage_area_m2']
    return {
        'population_covered': None, 'population_percentage': None, 'population_status': 'unavailable',
        'green_spaces_reached': selected['green_space_count'],
        'change_from_500_m': selected['green_space_count'] - baseline['green_space_count'],
        'total_accessible_area_ha': area,
        'accessible_area_percentage': min(100, max(0, selected['green_area_m2'] / zone * 100)) if measured and zone > 0 else None,
        'coverage_area_ha': zone / 10000,
        'point_records_without_footprint': missing,
        'area_status': 'complete' if missing == 0 else 'partial' if measured else 'unavailable',
    }
