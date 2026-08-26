"""
Tests for: reading a messy file.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from sampledata import orders_csv

from solution import check_shape, column_values, parse_rows, split_fields


class TestSplitFields(unittest.TestCase):
    def test_splits_a_plain_line(self):
        self.assertEqual(split_fields("a,b,c"), ["a", "b", "c"])

    def test_a_quoted_comma_stays_in_its_field(self):
        self.assertEqual(
            split_fields('1003,"1,499.00",pending'),
            ["1003", "1,499.00", "pending"],
            "a naive split turns the largest order in the file into 1 and loses "
            "the status, without raising anything",
        )

    def test_quotes_are_removed(self):
        self.assertEqual(split_fields('"a","b"'), ["a", "b"])

    def test_doubled_quotes_inside_a_quoted_field_become_one(self):
        self.assertEqual(split_fields('"say ""hi""",now'), ['say "hi"', "now"])

    def test_quotes_in_an_unquoted_field_are_literal(self):
        # `csv` does this, and getting it backwards silently rewrites data that
        # happens to contain a quote character.
        self.assertEqual(split_fields('say ""hi"",now'), ['say ""hi""', "now"])

    def test_an_empty_line_is_one_empty_field(self):
        self.assertEqual(split_fields(""), [""])

    def test_empty_fields_are_preserved(self):
        self.assertEqual(split_fields("a,,c"), ["a", "", "c"])

    def test_a_trailing_delimiter_makes_a_trailing_empty_field(self):
        self.assertEqual(split_fields("a,b,"), ["a", "b", ""])

    def test_honours_a_different_delimiter(self):
        self.assertEqual(split_fields("a|b|c", delimiter="|"), ["a", "b", "c"])


class TestParseRows(unittest.TestCase):
    def test_parses_the_sample_extract(self):
        rows = parse_rows(orders_csv())
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["order_id"], "1001")
        self.assertEqual(rows[0]["status"], "shipped")

    def test_keeps_the_quoted_total_intact(self):
        rows = parse_rows(orders_csv())
        self.assertEqual(rows[2]["total"], "1,499.00")

    def test_a_short_row_is_padded_not_dropped(self):
        rows = parse_rows(orders_csv())
        short = [row for row in rows if row["order_id"] == "1007"]
        self.assertEqual(len(short), 1, "a row present in the source must be present here")
        self.assertIsNone(
            short[0]["status"],
            "the field is missing, which is not the same as being empty",
        )

    def test_an_empty_field_is_an_empty_string(self):
        rows = parse_rows(orders_csv())
        blank = [row for row in rows if row["order_id"] == "1004"][0]
        self.assertEqual(
            blank["quantity"],
            "",
            "present and empty is not the same as absent, and the difference "
            "survives all the way to the quarantine in module 1",
        )

    def test_a_header_only_file_has_no_rows(self):
        self.assertEqual(parse_rows("a,b,c\n"), [])

    def test_empty_text_gives_no_rows(self):
        self.assertEqual(parse_rows(""), [])

    def test_extra_fields_are_dropped_to_the_header(self):
        rows = parse_rows("a,b\n1,2,3\n")
        self.assertEqual(rows, [{"a": "1", "b": "2"}])


class TestCheckShape(unittest.TestCase):
    def test_finds_the_short_row_in_the_sample(self):
        problems = check_shape(orders_csv())
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["expected"], 6)
        self.assertEqual(problems[0]["found"], 5)

    def test_line_numbers_count_the_header_as_line_one(self):
        problems = check_shape(orders_csv())
        # Order 1007 is the eighth record, so the eighth line after the header.
        self.assertEqual(
            problems[0]["line"],
            9,
            "an off-by-one here sends somebody to the wrong row in their editor",
        )

    def test_a_clean_file_reports_nothing(self):
        self.assertEqual(check_shape("a,b\n1,2\n3,4\n"), [])

    def test_reports_a_long_row_too(self):
        problems = check_shape("a,b\n1,2,3\n")
        self.assertEqual(problems, [{"line": 2, "expected": 2, "found": 3}])

    def test_does_not_raise_on_an_empty_file(self):
        self.assertEqual(check_shape(""), [])


class TestColumnValues(unittest.TestCase):
    def test_pulls_a_column(self):
        rows = parse_rows(orders_csv())
        self.assertEqual(len(column_values(rows, "order_id")), 10)

    def test_skips_blanks_and_missing(self):
        rows = parse_rows(orders_csv())
        # One quantity is empty and one row has no status field at all.
        self.assertEqual(len(column_values(rows, "quantity")), 9)
        self.assertEqual(len(column_values(rows, "status")), 9)

    def test_strips_whitespace(self):
        rows = parse_rows(orders_csv())
        self.assertIn("Grace@Example.com", column_values(rows, "customer"))

    def test_returns_stripped_values(self):
        rows = [{"customer": " Ada <ada@example.com> "}]

        self.assertEqual(column_values(rows, "customer"), ["Ada <ada@example.com>"])

    def test_an_unknown_column_gives_nothing(self):
        rows = parse_rows(orders_csv())
        self.assertEqual(column_values(rows, "not_a_column"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
