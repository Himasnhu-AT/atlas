"""
Tests for: indexes and the plan.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import create_index, explain, reads_every_row, same_rows

BY_CUSTOMER = "SELECT order_id FROM orders WHERE customer = ?"


def seeded() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE orders (
            order_id  INTEGER PRIMARY KEY,
            customer  TEXT NOT NULL,
            placed_at TEXT NOT NULL,
            total     TEXT NOT NULL
        )
        """
    )
    # Enough rows that the planner prefers an index once one exists. On a
    # handful of rows sqlite will correctly decide a scan is cheaper, and the
    # exercise would then be testing the planner's judgement rather than yours.
    rows = [
        (n, f"user{n % 50}@example.com", f"2026-03-{(n % 28) + 1:02d}", "10.00")
        for n in range(1, 2001)
    ]
    connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", rows)
    connection.commit()
    return connection


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = seeded()

    def tearDown(self):
        self.connection.close()


class TestExplain(Base):
    def test_returns_plan_lines(self):
        plan = explain(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertIsInstance(plan, list)
        self.assertGreater(len(plan), 0)
        self.assertIsInstance(plan[0], str)

    def test_an_unindexed_filter_scans(self):
        plan = explain(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertIn("SCAN", " ".join(plan).upper())

    def test_does_not_run_the_query(self):
        # EXPLAIN QUERY PLAN plans; it does not execute. A DELETE explained
        # should leave every row in place.
        explain(self.connection, "DELETE FROM orders WHERE order_id = ?", (1,))
        count = self.connection.execute("SELECT count(*) FROM orders").fetchone()[0]
        self.assertEqual(count, 2000)


class TestReadsEveryRow(unittest.TestCase):
    def test_recognises_a_scan(self):
        self.assertTrue(reads_every_row(["SCAN orders"]))

    def test_recognises_a_search(self):
        self.assertFalse(
            reads_every_row(["SEARCH orders USING INDEX orders_customer (customer=?)"])
        )

    def test_any_scan_counts(self):
        plan = [
            "SEARCH customers USING INDEX customers_email (email=?)",
            "SCAN orders",
        ]
        self.assertTrue(
            reads_every_row(plan),
            "a multi-table plan may search one table and scan another",
        )

    def test_an_empty_plan_reads_nothing(self):
        self.assertFalse(reads_every_row([]))


class TestCreateIndex(Base):
    def test_turns_a_scan_into_a_search(self):
        before = explain(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertTrue(reads_every_row(before))

        create_index(self.connection, "orders_customer", "orders", ["customer"])

        after = explain(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertFalse(
            reads_every_row(after),
            f"still scanning after the index was created: {after}",
        )
        self.assertIn("orders_customer", " ".join(after))

    def test_is_safe_to_run_twice(self):
        create_index(self.connection, "orders_customer", "orders", ["customer"])
        create_index(self.connection, "orders_customer", "orders", ["customer"])

    def test_creates_a_composite_index_in_order(self):
        create_index(self.connection, "orders_cp", "orders", ["customer", "placed_at"])
        plan = explain(
            self.connection,
            "SELECT order_id FROM orders WHERE customer = ? AND placed_at = ?",
            ("user1@example.com", "2026-03-02"),
        )
        self.assertFalse(reads_every_row(plan))

    def test_a_composite_index_does_not_help_its_second_column_alone(self):
        create_index(self.connection, "orders_cp", "orders", ["customer", "placed_at"])
        plan = explain(
            self.connection,
            "SELECT order_id FROM orders WHERE placed_at = ?",
            ("2026-03-02",),
        )
        self.assertTrue(
            reads_every_row(plan),
            "leftmost prefix: a phone book sorted by surname then first name "
            "cannot find every Aditi",
        )

    def test_refuses_an_identifier_it_cannot_vouch_for(self):
        for bad in ["orders; DROP TABLE orders", "a b", "", "1;--"]:
            with self.assertRaises(ValueError, msg=bad):
                create_index(self.connection, bad, "orders", ["customer"])
        with self.assertRaises(ValueError):
            create_index(self.connection, "ok", "orders", ["customer); DROP TABLE orders --"])


class TestSameRows(Base):
    def test_an_index_changes_the_speed_and_nothing_else(self):
        before = same_rows(self.connection, BY_CUSTOMER, ("user1@example.com",))
        create_index(self.connection, "orders_customer", "orders", ["customer"])
        after = same_rows(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertEqual(
            before,
            after,
            "a query returning different rows with an index than without means "
            "something is wrong with the query, not the index",
        )
        self.assertGreater(len(before), 0)

    def test_sorts_so_order_is_not_part_of_the_comparison(self):
        rows = same_rows(self.connection, "SELECT order_id FROM orders LIMIT 5")
        self.assertEqual(rows, sorted(rows))

    def test_returns_tuples(self):
        rows = same_rows(self.connection, BY_CUSTOMER, ("user1@example.com",))
        self.assertIsInstance(rows[0], tuple)


if __name__ == "__main__":
    unittest.main(verbosity=2)
