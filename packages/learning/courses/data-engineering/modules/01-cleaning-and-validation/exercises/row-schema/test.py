"""
Tests for: a schema that reports.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from sampledata import orders_csv, read_rows

from solution import is_usable, validate_extract, validate_row


def to_int(raw):
    try:
        return int(str(raw).strip()), True
    except (ValueError, AttributeError):
        return None, False


def to_text(raw):
    text = str(raw).strip()
    return (text, True) if text else (None, False)


RULES = [
    {"name": "order_id", "coerce": to_int, "required": True},
    {"name": "customer", "coerce": to_text, "required": True},
    {"name": "quantity", "coerce": to_int, "required": False},
    {"name": "status", "coerce": to_text, "required": True},
]


class TestValidateRow(unittest.TestCase):
    def test_a_good_row_is_valid(self):
        row = {"order_id": "1001", "customer": "a@b.c", "quantity": "2", "status": "shipped"}
        result = validate_row(row, RULES, 2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["values"]["order_id"], 1001)
        self.assertEqual(result["values"]["quantity"], 2)

    def test_carries_the_source_row_number(self):
        result = validate_row({"order_id": "1"}, RULES, 47)
        self.assertEqual(
            result["row"], 47, "renumbering makes every error point at the wrong line"
        )

    def test_a_missing_required_field_is_missing_not_invalid(self):
        row = {"order_id": "1001", "customer": "a@b.c", "quantity": "2", "status": None}
        result = validate_row(row, RULES, 2)
        problems = {(e["field"], e["problem"]) for e in result["errors"]}
        self.assertIn(("status", "missing"), problems)

    def test_an_empty_required_field_is_also_missing(self):
        row = {"order_id": "1001", "customer": "", "quantity": "2", "status": "shipped"}
        result = validate_row(row, RULES, 2)
        problems = {(e["field"], e["problem"]) for e in result["errors"]}
        self.assertIn(("customer", "missing"), problems)

    def test_an_unreadable_value_is_invalid_not_missing(self):
        row = {"order_id": "1001", "customer": "a@b.c", "quantity": "unknown", "status": "s"}
        result = validate_row(row, RULES, 2)
        self.assertEqual(
            [(e["field"], e["problem"]) for e in result["errors"]],
            [("quantity", "invalid")],
            "the source sending nonsense is a different failure from the source "
            "not sending anything, and they have different owners",
        )

    def test_an_error_keeps_the_offending_value(self):
        row = {"order_id": "1001", "customer": "a@b.c", "quantity": "unknown", "status": "s"}
        result = validate_row(row, RULES, 2)
        self.assertEqual(result["errors"][0]["value"], "unknown")

    def test_an_optional_field_may_be_absent(self):
        row = {"order_id": "1001", "customer": "a@b.c", "quantity": "", "status": "shipped"}
        result = validate_row(row, RULES, 2)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["values"]["quantity"])

    def test_every_field_appears_in_values(self):
        row = {"order_id": "nope", "customer": "a@b.c", "quantity": "2", "status": "shipped"}
        result = validate_row(row, RULES, 2)
        self.assertEqual(
            set(result["values"]),
            {rule["name"] for rule in RULES},
            "the shape is the same for every row, so a caller never has to "
            "check whether a key exists",
        )
        self.assertIsNone(result["values"]["order_id"])


class TestValidateExtract(unittest.TestCase):
    def setUp(self):
        self.report = validate_extract(read_rows(orders_csv()), RULES)

    def test_splits_valid_from_broken(self):
        self.assertEqual(len(self.report["valid"]) + len(self.report["broken"]), 10)
        self.assertGreater(len(self.report["broken"]), 0)

    def test_finds_the_known_problems_in_the_sample(self):
        problems = self.report["field_problems"]
        # Order 1006 has quantity "unknown"; 1008 has no customer; 1007 is short
        # so its status is absent.
        self.assertEqual(problems.get("quantity"), 1)
        self.assertEqual(problems.get("customer"), 1)
        self.assertEqual(problems.get("status"), 1)

    def test_counts_rows_not_errors(self):
        rows = [{"order_id": None, "customer": None, "quantity": "2", "status": None}]
        report = validate_extract(rows, RULES)
        self.assertEqual(report["field_problems"]["order_id"], 1)
        self.assertEqual(len(report["broken"][0]["errors"]), 3)

    def test_numbers_rows_from_the_second_line(self):
        report = validate_extract(read_rows(orders_csv()), RULES)
        first = (report["valid"] + report["broken"])[0]
        self.assertEqual(first["row"], 2, "line 1 of a CSV is the header")

    def test_honours_a_different_starting_number(self):
        report = validate_extract([{"order_id": "1"}], RULES, first_row_number=500)
        self.assertEqual(report["broken"][0]["row"], 500)

    def test_an_empty_extract_reports_nothing(self):
        report = validate_extract([], RULES)
        self.assertEqual(report["valid"], [])
        self.assertEqual(report["broken"], [])
        self.assertEqual(report["field_problems"], {})


class TestIsUsable(unittest.TestCase):
    def test_a_clean_extract_is_usable(self):
        report = {"valid": [{}] * 100, "broken": [], "field_problems": {}}
        self.assertTrue(is_usable(report))

    def test_a_little_breakage_is_tolerated(self):
        report = {"valid": [{}] * 99, "broken": [{}], "field_problems": {}}
        self.assertTrue(is_usable(report, max_broken_ratio=0.01))

    def test_too_much_breakage_is_not(self):
        report = {"valid": [{}] * 90, "broken": [{}] * 10, "field_problems": {}}
        self.assertFalse(is_usable(report, max_broken_ratio=0.01))

    def test_an_empty_extract_is_not_usable(self):
        self.assertFalse(
            is_usable({"valid": [], "broken": [], "field_problems": {}}),
            "an empty file is usually a failed export, and treating it as "
            "nothing to do is how a pipeline reports success having loaded nothing",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
