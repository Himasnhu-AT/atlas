"""
Tests for: shapes that nest.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import double_counted, explode, flatten, schema_of

ORDER = {
    "order_id": 1003,
    "customer": {"email": "lin@example.com", "country": "SG"},
    "items": [
        {"sku": "A-1", "quantity": 2},
        {"sku": "B-7", "quantity": 1},
    ],
    "total": 1499.00,
}


class TestFlatten(unittest.TestCase):
    def test_flattens_one_level(self):
        self.assertEqual(flatten({"a": 1, "b": {"c": 2}}), {"a": 1, "b.c": 2})

    def test_flattens_several_levels(self):
        self.assertEqual(flatten({"a": {"b": {"c": 3}}}), {"a.b.c": 3})

    def test_leaves_a_list_alone(self):
        flat = flatten(ORDER)
        self.assertEqual(
            flat["items"],
            ORDER["items"],
            "flattening a list into items.0.sku makes the column names depend "
            "on how many items an order had, so two orders get two schemas",
        )

    def test_keeps_scalars_and_their_types(self):
        flat = flatten(ORDER)
        self.assertEqual(flat["order_id"], 1003)
        self.assertEqual(flat["customer.email"], "lin@example.com")
        self.assertIsInstance(flat["total"], float)

    def test_an_empty_document_is_empty(self):
        self.assertEqual(flatten({}), {})

    def test_an_empty_nested_dict_contributes_nothing(self):
        self.assertEqual(flatten({"a": 1, "b": {}}), {"a": 1})

    def test_honours_a_different_separator(self):
        self.assertEqual(flatten({"a": {"b": 1}}, separator="__"), {"a__b": 1})

    def test_none_is_a_value_not_a_gap(self):
        self.assertEqual(flatten({"a": None}), {"a": None})


class TestExplode(unittest.TestCase):
    def test_one_row_per_element(self):
        rows = explode(ORDER, "items")
        self.assertEqual(len(rows), 2)

    def test_each_row_carries_the_parent(self):
        rows = explode(ORDER, "items")
        self.assertEqual(rows[0]["order_id"], 1003)
        self.assertEqual(rows[0]["customer.email"], "lin@example.com")
        self.assertEqual(rows[0]["sku"], "A-1")
        self.assertEqual(rows[1]["sku"], "B-7")

    def test_the_list_field_is_gone(self):
        for row in explode(ORDER, "items"):
            self.assertNotIn("items", row)

    def test_an_empty_list_makes_no_rows(self):
        self.assertEqual(
            explode({"order_id": 1, "items": []}, "items"),
            [],
            "an order with no items produced no item rows, and inventing one "
            "puts a row in the table for something that does not exist",
        )

    def test_a_missing_field_makes_no_rows(self):
        self.assertEqual(explode({"order_id": 1}, "items"), [])

    def test_the_element_wins_a_collision(self):
        rows = explode({"id": 1, "sku": "parent", "items": [{"sku": "child"}]}, "items")
        self.assertEqual(rows[0]["sku"], "child")


class TestDoubleCounted(unittest.TestCase):
    def test_finds_the_classic_explode_bug(self):
        rows = explode(ORDER, "items")
        report = double_counted(rows, "order_id", "total")
        self.assertEqual(report["keys"], ["1003"])
        self.assertAlmostEqual(report["naive_sum"], 2998.0)
        self.assertAlmostEqual(
            report["true_sum"],
            1499.0,
            msg="the naive sum looks plausible, which is what makes this bug "
            "survive review",
        )

    def test_reports_nothing_when_keys_are_unique(self):
        rows = [{"id": "1", "total": 10.0}, {"id": "2", "total": 20.0}]
        report = double_counted(rows, "id", "total")
        self.assertEqual(report["keys"], [])
        self.assertAlmostEqual(report["naive_sum"], 30.0)
        self.assertAlmostEqual(report["true_sum"], 30.0)

    def test_reads_numbers_written_as_strings(self):
        rows = [{"id": "1", "total": "5.5"}, {"id": "1", "total": "5.5"}]
        report = double_counted(rows, "id", "total")
        self.assertAlmostEqual(report["naive_sum"], 11.0)
        self.assertAlmostEqual(report["true_sum"], 5.5)

    def test_skips_values_it_cannot_read(self):
        rows = [{"id": "1", "total": "n/a"}, {"id": "2", "total": 4.0}]
        report = double_counted(rows, "id", "total")
        self.assertAlmostEqual(
            report["naive_sum"],
            4.0,
            msg="a value nobody can read is not evidence that the value was nothing",
        )

    def test_sorts_the_repeated_keys(self):
        rows = [
            {"id": "b", "total": 1.0},
            {"id": "b", "total": 1.0},
            {"id": "a", "total": 2.0},
            {"id": "a", "total": 2.0},
        ]
        self.assertEqual(double_counted(rows, "id", "total")["keys"], ["a", "b"])

    def test_empty_input_is_zeroes(self):
        report = double_counted([], "id", "total")
        self.assertEqual(report["keys"], [])
        self.assertEqual(report["naive_sum"], 0)
        self.assertEqual(report["true_sum"], 0)


class TestSchemaOf(unittest.TestCase):
    def test_counts_each_field(self):
        rows = [{"a": 1, "b": 2}, {"a": 3}]
        self.assertEqual(schema_of(rows), {"a": 2, "b": 1})

    def test_counts_a_field_that_is_present_and_none(self):
        rows = [{"a": None}, {"a": 1}]
        self.assertEqual(
            schema_of(rows),
            {"a": 2},
            "present and null is not the same as absent, and this is the "
            "cheapest place to keep the difference",
        )

    def test_empty_rows_give_an_empty_schema(self):
        self.assertEqual(schema_of([]), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
