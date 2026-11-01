import unittest
from greenspaces.map_queries import parse_map_query


class MapQueryTests(unittest.TestCase):
    def test_defaults(self):
        query = parse_map_query({})
        self.assertEqual(query.page, 1)
        self.assertIsNone(query.bbox)

    def test_valid_bbox_search_and_category(self):
        query = parse_map_query({"bbox": "101,2,102,4", "q": " Park ", "category": "2", "page": "3"})
        self.assertEqual(query.bbox, (101, 2, 102, 4))
        self.assertEqual((query.search, query.category, query.page), ("Park", 2, 3))

    def test_invalid_and_nonfinite_bounds(self):
        for bbox in ("", "1,2,3", "1,2,3,4,5", "NaN,2,3,4", "1,2,Infinity,4", "1,4,3,2",
                     "3,2,1,4", "1,2,1,4", "-181,2,3,4", "1,-91,3,4", "bad"):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                parse_map_query({"bbox": bbox})

    def test_invalid_pages_and_categories(self):
        for field in ("page", "category"):
            for value in ("0", "-1", "1.5", "true", "2147483648", "x", "١"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    parse_map_query({field: value})
        with self.assertRaises(ValueError):
            parse_map_query({"page": "10001"})

    def test_unknown_parameters(self):
        with self.assertRaises(ValueError):
            parse_map_query({"dataset": "1"})

    def test_boundaries_reject_search_parameters(self):
        with self.assertRaises(ValueError):
            parse_map_query({"q": "test"}, allow_search=False)

    def test_search_length_limit(self):
        with self.assertRaises(ValueError):
            parse_map_query({"q": "x" * 151})

    def test_duplicate_parameters(self):
        class MultiValues(dict):
            def getlist(self, key):
                return ["1", "2"]
        with self.assertRaises(ValueError):
            parse_map_query(MultiValues(page="1"))
