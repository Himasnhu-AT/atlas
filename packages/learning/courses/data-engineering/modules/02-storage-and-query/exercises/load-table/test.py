"""
Tests for: loading a table.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import create_schema, duplicate_keys, load_orders, row_count

CLEAN_ROWS = [
    {
        "order_id": 1001,
        "customer": "ada@example.com",
        "placed_at": "2026-03-01",
        "quantity": 2,
        "total": "49.90",
        "status": "shipped",
    },
    {
        "order_id": 1003,
        "customer": "lin@example.com",
        "placed_at": "2026-03-02",
        "quantity": 3,
        "total": "1499.00",
        "status": "pending",
    },
    # The retried export, identical to the row above it.
    {
        "order_id": 1003,
        "customer": "lin@example.com",
        "placed_at": "2026-03-02",
        "quantity": 3,
        "total": "1499.00",
        "status": "pending",
    },
    {
        "order_id": 1004,
        "customer": "ada@example.com",
        "placed_at": "2026-03-02",
        "quantity": None,
        "total": "29.99",
        "status": "shipped",
    },
]


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        create_schema(self.connection)

    def tearDown(self):
        self.connection.close()


class TestSchema(Base):
    def test_creates_the_table(self):
        self.assertEqual(row_count(self.connection), 0)

    def test_is_safe_to_run_twice(self):
        create_schema(self.connection)
        self.assertEqual(row_count(self.connection), 0)

    def test_quantity_is_the_only_nullable_column(self):
        columns = {
            row[1]: row[3]  # name -> notnull flag
            for row in self.connection.execute("PRAGMA table_info(orders)")
        }
        self.assertEqual(columns["quantity"], 0, "an order can ship without a known quantity")
        for name in ["customer", "placed_at", "total", "status"]:
            self.assertEqual(columns[name], 1, f"{name} must not be nullable")

    def test_order_id_is_the_primary_key(self):
        keys = [row[1] for row in self.connection.execute("PRAGMA table_info(orders)") if row[5]]
        self.assertEqual(keys, ["order_id"])


class TestDuplicateKeys(unittest.TestCase):
    def test_finds_an_identical_duplicate(self):
        report = duplicate_keys(CLEAN_ROWS)
        self.assertEqual(report["identical"], [1003])
        self.assertEqual(report["conflicting"], [])

    def test_finds_a_conflicting_duplicate(self):
        rows = [
            {"order_id": 1, "status": "pending"},
            {"order_id": 1, "status": "shipped"},
        ]
        report = duplicate_keys(rows)
        self.assertEqual(
            report["conflicting"],
            [1],
            "keeping the first is only honest when the duplicates agree",
        )
        self.assertEqual(report["identical"], [])

    def test_a_conflict_anywhere_beats_a_match(self):
        rows = [
            {"order_id": 1, "status": "a"},
            {"order_id": 1, "status": "a"},
            {"order_id": 1, "status": "b"},
        ]
        report = duplicate_keys(rows)
        self.assertEqual(report["conflicting"], [1])
        self.assertEqual(report["identical"], [])

    def test_unique_rows_report_nothing(self):
        rows = [{"order_id": 1}, {"order_id": 2}]
        self.assertEqual(duplicate_keys(rows), {"identical": [], "conflicting": []})

    def test_sorts_both_lists(self):
        rows = [{"order_id": k} for k in [3, 3, 1, 1, 2, 2]]
        self.assertEqual(duplicate_keys(rows)["identical"], [1, 2, 3])

    def test_empty_rows_report_nothing(self):
        self.assertEqual(duplicate_keys([]), {"identical": [], "conflicting": []})


class TestLoad(Base):
    def test_reports_what_it_did(self):
        report = load_orders(self.connection, CLEAN_ROWS)
        self.assertEqual(report["received"], 4)
        self.assertEqual(report["written"], 3)
        self.assertEqual(
            report["skipped"],
            1,
            'a load that says "done" tells you nothing',
        )

    def test_writes_the_rows(self):
        load_orders(self.connection, CLEAN_ROWS)
        self.assertEqual(row_count(self.connection), 3)

    def test_keeps_a_null_quantity(self):
        load_orders(self.connection, CLEAN_ROWS)
        value = self.connection.execute(
            "SELECT quantity FROM orders WHERE order_id = 1004"
        ).fetchone()[0]
        self.assertIsNone(value)

    def test_stores_the_total_exactly(self):
        load_orders(self.connection, CLEAN_ROWS)
        value = self.connection.execute(
            "SELECT total FROM orders WHERE order_id = 1003"
        ).fetchone()[0]
        self.assertEqual(
            value,
            "1499.00",
            "money is stored as the exact decimal, because a column of floats "
            "drifts until a report is out by a cent",
        )

    def test_running_the_same_load_twice_writes_nothing_new(self):
        load_orders(self.connection, CLEAN_ROWS)
        second = load_orders(self.connection, CLEAN_ROWS)
        self.assertEqual(second["written"], 0)
        self.assertEqual(row_count(self.connection), 3)

    def test_survives_a_value_containing_a_quote(self):
        rows = [
            {
                "order_id": 2001,
                "customer": "o'brien@example.com",
                "placed_at": "2026-03-01",
                "quantity": 1,
                "total": "10.00",
                "status": "shipped",
            }
        ]
        load_orders(self.connection, rows)
        value = self.connection.execute(
            "SELECT customer FROM orders WHERE order_id = 2001"
        ).fetchone()[0]
        self.assertEqual(
            value,
            "o'brien@example.com",
            "in a pipeline the attacker is usually an apostrophe in a name",
        )

    def test_an_empty_load_is_not_an_error(self):
        report = load_orders(self.connection, [])
        self.assertEqual(report, {"received": 0, "written": 0, "skipped": 0})

    def test_a_broken_row_leaves_nothing_behind(self):
        rows = list(CLEAN_ROWS) + [{"order_id": 9999, "customer": None}]
        with self.assertRaises(Exception):
            load_orders(self.connection, rows)
        self.assertEqual(
            row_count(self.connection),
            0,
            "one transaction means the load either happened or it did not",
        )


class TestRowCount(Base):
    def test_counts(self):
        load_orders(self.connection, CLEAN_ROWS)
        self.assertEqual(row_count(self.connection, "orders"), 3)

    def test_refuses_a_table_it_does_not_know(self):
        with self.assertRaises(ValueError):
            row_count(self.connection, "orders; DROP TABLE orders")


if __name__ == "__main__":
    unittest.main(verbosity=2)
