import unittest
from greenspaces.coverage_queries import coverage_metrics, parse_coverage


def band(radius, count=2, points=0, polygons=2, area=10000):
    return {'radius_m': radius, 'green_space_count': count, 'point_count': points,
            'polygon_count': polygons, 'coverage_area_m2': 1000000, 'green_area_m2': area}


class CoverageQueryTests(unittest.TestCase):
    def test_valid_request_and_distance_limits(self):
        for radius in (100, 500, 1000, 2000, 10000):
            query = parse_coverage({'latitude': 3.08, 'longitude': 101.6, 'radius_m': radius})
            self.assertEqual(query.radius_m, radius)

    def test_strict_fields_and_bad_values(self):
        valid = {'latitude': 3.08, 'longitude': 101.6, 'radius_m': 1000}
        for data in (None, [], {}, {**valid, 'page': 1}, {**valid, 'radius_m': 0},
                     {**valid, 'radius_m': True}, {**valid, 'latitude': float('nan')}):
            with self.assertRaises(ValueError):
                parse_coverage(data)

    def test_area_units_and_real_baseline_comparison(self):
        result = coverage_metrics([band(500, count=1), band(1000, count=3)], 1000)
        self.assertEqual(result['total_accessible_area_ha'], 1)
        self.assertEqual(result['coverage_area_ha'], 100)
        self.assertEqual(result['accessible_area_percentage'], 1)
        self.assertEqual(result['change_from_500_m'], 2)

    def test_unknown_population_is_not_zero(self):
        result = coverage_metrics([band(500)], 500)
        self.assertIsNone(result['population_covered'])
        self.assertIsNone(result['population_percentage'])
        self.assertEqual(result['population_status'], 'unavailable')

    def test_point_only_area_is_unavailable(self):
        result = coverage_metrics([band(500, points=2, polygons=0, area=0)], 500)
        self.assertIsNone(result['total_accessible_area_ha'])
        self.assertIsNone(result['accessible_area_percentage'])
        self.assertEqual(result['area_status'], 'unavailable')

    def test_mixed_geometry_is_marked_partial_and_empty_is_real_zero(self):
        mixed = coverage_metrics([band(500, points=1, polygons=1)], 500)
        self.assertEqual((mixed['area_status'], mixed['point_records_without_footprint']), ('partial', 1))
        empty = coverage_metrics([band(500, count=0, polygons=0, area=0)], 500)
        self.assertEqual((empty['total_accessible_area_ha'], empty['area_status']), (0, 'complete'))
