import csv
import io
import unittest
from decimal import Decimal

from greenspaces.csv_schema import COLUMNS, MAX_BYTES, MAX_ROWS, CsvFileError, decode_csv, parse_csv


def make_csv(rows, columns=COLUMNS):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(field, "") for field in columns])
    return output.getvalue().encode("utf-8")


class CsvSchemaTests(unittest.TestCase):
    def row(self, **changes):
        row = {"name": "TEST park", "area_id": "1", "category_id": "2",
               "latitude": "3.100000", "longitude": "101.600000", "area_size": "1.2500"}
        return {**row, **changes}

    def test_valid_point_and_decimal_types(self):
        batch = parse_csv(make_csv([self.row()]))
        self.assertEqual(batch.total_records, 1)
        self.assertEqual(batch.issues, [])
        self.assertEqual(batch.rows[0].row_number, 2)
        self.assertEqual(batch.rows[0].values["area_id"], 1)
        self.assertEqual(batch.rows[0].values["area_size"], Decimal("1.2500"))

    def test_utf8_bom_non_ascii_and_quoted_multiline_fields(self):
        row = self.row(name="TEST Taman 绿色", description='Has a comma, a "quote"\nand a newline')
        batch = parse_csv(b"\xef\xbb\xbf" + make_csv([row]))
        self.assertEqual(batch.issues, [])
        self.assertEqual(batch.rows[0].values["description"], row["description"])
        self.assertEqual(batch.rows[0].values["name"], row["name"])

    def test_header_order_and_optional_columns(self):
        batch = parse_csv(make_csv([self.row()], ("longitude", "category_id", "latitude", "area_id", "name")))
        self.assertEqual(batch.issues, [])
        self.assertIsNone(batch.rows[0].values["area_size"])

    def test_whitespace_and_blank_lines(self):
        batch = parse_csv(make_csv([self.row(name="  TEST park  ")]) + b"\n,,,\n")
        self.assertEqual(batch.total_records, 1)
        self.assertEqual(batch.rows[0].values["name"], "TEST park")

    def test_wkt_can_replace_coordinates(self):
        batch = parse_csv(make_csv([self.row(latitude="", longitude="", geometry_wkt="POINT (101.6 3.1)")]))
        self.assertEqual(batch.issues, [])
        self.assertIsNone(batch.rows[0].values["latitude"])

    def test_rejects_missing_duplicate_unknown_and_geometry_headers(self):
        for header in ("name,name,area_id,category_id,latitude,longitude\n",
                       "name,area_id,latitude,longitude\n", "name,area_id,category_id,lat,lon\n",
                       "name,area_id,category_id\n"):
            with self.subTest(header=header), self.assertRaises(CsvFileError):
                parse_csv(header.encode())

    def test_rejects_empty_header_only_binary_and_invalid_encoding(self):
        for raw in (b"", b"\n", make_csv([]), b"\xff\xfe", b"abc\x00def", b"x" * (MAX_BYTES + 1)):
            with self.subTest(length=len(raw)), self.assertRaises(CsvFileError):
                parse_csv(raw)

    def test_rejects_malformed_quotes_and_wrong_column_count(self):
        for raw in (b'name,area_id,category_id,latitude,longitude\n"unterminated',
                    b"name,area_id,category_id,latitude,longitude\npark,1,2,3,101,extra\n"):
            with self.assertRaises(CsvFileError):
                parse_csv(raw)

    def test_row_limit(self):
        with self.assertRaisesRegex(CsvFileError, "1,000"):
            parse_csv(make_csv([self.row()] * (MAX_ROWS + 1)))

    def test_coordinate_ranges_precision_nonfinite_and_pair(self):
        for changes in ({"latitude": "91"}, {"longitude": "-181"}, {"latitude": "NaN"},
                        {"longitude": "Infinity"}, {"latitude": "3.1234567"},
                        {"latitude": "1e1"}, {"latitude": ""}, {"latitude": "", "longitude": ""}):
            with self.subTest(changes=changes):
                batch = parse_csv(make_csv([self.row(**changes)]))
                self.assertTrue(batch.issues)
                self.assertEqual(batch.rows, [])

    def test_coordinate_extremes_are_valid(self):
        for latitude, longitude in (("-90", "-180"), ("90", "180"), ("0", "0")):
            self.assertEqual(parse_csv(make_csv([self.row(latitude=latitude, longitude=longitude)])).issues, [])

    def test_invalid_ids_name_area_size_and_text_length(self):
        for changes in ({"area_id": "1.0"}, {"category_id": "-1"}, {"area_id": "2147483648"},
                        {"area_id": ""}, {"name": " "}, {"name": "x" * 151},
                        {"area_size": "-1"}, {"area_size": "10000000000"},
                        {"area_size": "1.12345"}, {"description": "x" * 20001}):
            with self.subTest(changes=changes):
                self.assertTrue(parse_csv(make_csv([self.row(**changes)])).issues)

    def test_unsupported_wkt_and_srid_prefix(self):
        for geometry in ("SRID=3857;POINT (1 2)", "LINESTRING (1 2, 3 4)", "POINT EMPTY", "POINT Z (1 2 3)"):
            self.assertTrue(parse_csv(make_csv([self.row(geometry_wkt=geometry)])).issues)

    def test_keeps_errors_separate_from_valid_rows(self):
        batch = parse_csv(make_csv([self.row(), self.row(name="", latitude="91")]))
        self.assertEqual(batch.total_records, 2)
        self.assertEqual(len(batch.rows), 1)
        self.assertEqual({issue.row_number for issue in batch.issues}, {3})
        self.assertEqual({issue.field_name for issue in batch.issues}, {"name", "latitude"})


if __name__ == "__main__":
    unittest.main()
