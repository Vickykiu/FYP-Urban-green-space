"""FR6 input and measurement contracts, without native GIS dependencies."""
from .map_queries import positive_integer


def parse_dashboard(params):
    if set(params) - {'area', 'category'}:
        raise ValueError('Unsupported dashboard filter.')
    if hasattr(params, 'getlist') and any(len(params.getlist(key)) != 1 for key in params):
        raise ValueError('Supply each filter once.')
    return {key: positive_integer(params[key], key) if key in params else None for key in ('area', 'category')}


def dashboard_metrics(row):
    count, points = row['space_count'], row['point_count']
    measured = count == 0 or points < count
    return {
        'space_count': count, 'point_count': points,
        'green_area_ha': row['green_area_m2'] / 10000 if measured else None,
        'area_status': 'complete' if points == 0 else 'partial' if measured else 'unavailable',
        'zone_area_ha': row['zone_area_m2'] / 10000,
        'covered_land_ha': min(row['covered_land_m2'], row['zone_area_m2']) / 10000,
        'coverage_percentage': min(100, max(0, row['covered_land_m2'] / row['zone_area_m2'] * 100)),
        'population_covered': None, 'population_gap': None, 'planning_gaps': None,
        'baseline_change_percentage': None,
    }
