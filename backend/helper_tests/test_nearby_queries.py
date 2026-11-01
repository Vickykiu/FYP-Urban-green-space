import unittest
from greenspaces.nearby_queries import parse_nearby, parse_place_search


class NearbyQueryTests(unittest.TestCase):
    def query(self, **values):
        return parse_nearby({'latitude': 3.1, 'longitude': 101.6, 'radius_m': 1000, **values})

    def test_valid_coordinates_radius_and_page(self):
        result = self.query(latitude='3.100000', longitude='101.600000', radius_m='500', page=2)
        self.assertEqual((result.latitude, result.longitude, result.radius_m, result.page), (3.1, 101.6, 500, 2))

    def test_radius_limits(self):
        self.assertEqual(self.query(radius_m=100).radius_m, 100)
        self.assertEqual(self.query(radius_m=10000).radius_m, 10000)
        for value in (0, -1, 99, 10001, 500.5, True, None, 'NaN', float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError): self.query(radius_m=value)

    def test_coordinate_limits_and_bad_types(self):
        for key, value in [('latitude', 91), ('longitude', 181), ('latitude', -91), ('longitude', -181),
                           ('latitude', True), ('longitude', []), ('latitude', ''), ('longitude', None),
                           ('latitude', 'nan'), ('longitude', 'Infinity'), ('latitude', '1' * 100)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.query(**{key: value})

    def test_missing_or_unknown_fields(self):
        for value in ({}, [], None, {'latitude': 3, 'longitude': 101},
                      {'latitude': 3, 'longitude': 101, 'radius_m': 1000, 'administrator': 1}):
            with self.assertRaises(ValueError): parse_nearby(value)

    def test_page_validation(self):
        for value in (0, -1, 1.1, 10001, True, 'nan'):
            with self.assertRaises(ValueError): self.query(page=value)

    def test_place_names_trim_but_keep_unicode(self):
        self.assertEqual(parse_place_search({'q': '  Taman café  '}), 'Taman café')

    def test_invalid_place_search(self):
        for value in ({}, {'q': ''}, {'q': 'x'}, {'q': 'x' * 151}, {'q': None}, {'q': 'a\nb'}, {'q': 'Park', 'id': 2}):
            with self.assertRaises(ValueError): parse_place_search(value)
