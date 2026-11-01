import unittest
from greenspaces.dashboard_queries import dashboard_metrics, parse_dashboard


class DashboardQueryTests(unittest.TestCase):
    def test_defaults_and_ids(self):
        self.assertEqual(parse_dashboard({}), {'area': None, 'category': None})
        self.assertEqual(parse_dashboard({'area': '2', 'category': '3'}), {'area': 2, 'category': 3})

    def test_invalid_and_unknown_filters(self):
        for value in ('', '0', '-1', '1.5', 'true', 'NaN', '2147483648', '١', True, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_dashboard({'area': value})
        with self.assertRaises(ValueError):
            parse_dashboard({'radius_m': '1000'})

    def test_duplicate_filters(self):
        class Repeated(dict):
            def getlist(self, key):
                return ['1', '2']
        with self.assertRaises(ValueError):
            parse_dashboard(Repeated(area='1'))

    def row(self, **changes):
        return {'space_count': 2, 'point_count': 1, 'green_area_m2': 20000,
                'covered_land_m2': 600000, 'zone_area_m2': 1000000, **changes}

    def test_area_units_and_land_percentage(self):
        metrics = dashboard_metrics(self.row())
        self.assertEqual((metrics['green_area_ha'], metrics['zone_area_ha'], metrics['covered_land_ha']), (2, 100, 60))
        self.assertEqual((metrics['coverage_percentage'], metrics['area_status']), (60, 'partial'))

    def test_population_priorities_and_baseline_remain_unknown(self):
        metrics = dashboard_metrics(self.row())
        for key in ('population_covered', 'population_gap', 'planning_gaps', 'baseline_change_percentage'):
            self.assertIsNone(metrics[key])

    def test_point_only_unknown_footprint_is_not_zero(self):
        metrics = dashboard_metrics(self.row(space_count=1, point_count=1, green_area_m2=0))
        self.assertIsNone(metrics['green_area_ha'])
        self.assertEqual(metrics['area_status'], 'unavailable')
        self.assertEqual(metrics['coverage_percentage'], 60)

    def test_empty_selection_is_zero_and_roundoff_is_clamped(self):
        metrics = dashboard_metrics(self.row(space_count=0, point_count=0, green_area_m2=0, covered_land_m2=0))
        self.assertEqual((metrics['green_area_ha'], metrics['coverage_percentage'], metrics['area_status']), (0, 0, 'complete'))
        metrics = dashboard_metrics(self.row(covered_land_m2=1000000.01))
        self.assertEqual((metrics['coverage_percentage'], metrics['covered_land_ha']), (100, 100))
