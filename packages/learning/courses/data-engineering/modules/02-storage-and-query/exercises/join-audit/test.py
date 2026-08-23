"""
Tests for: the rows a join loses.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import join_is_safe, joined_count, multiplying_keys, unmatched_orders

ORDERS = [
    (1001, "ada@example.com"),
    (1002, " Grace@Example.com "),  # the same person, spelled differently
    (1003, "lin@example.com"),
    (1005, "kofi@example.com"),
    (1006, "mei@example.com"),
    (1008, ""),                      # no customer at all
    (1010, "nobody@example.com"),    # a real value that matches nothing
]

CUSTOMERS = [
    ("ada@example.com", "GB"),
    ("grace@example.com", "GB"),
    ("lin@example.com", "SG"),
    ("kofi@example.com", "GH"),
    ("mei@example.com", "SG"),
]


def seeded(customers=CUSTOMERS) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer TEXT)")
    connection.execute("CREATE TABLE customers (email TEXT, country TEXT)")
    connection.executemany("INSERT INTO orders VALUES (?, ?)", ORDERS)
    connection.executemany("INSERT INTO customers VALUES (?, ?)", customers)
    connection.commit()
    return connection


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = seeded()

    def tearDown(self):
        self.connection.close()


class TestJoinedCount(Base):
    def test_counts_what_the_join_kept_and_lost(self):
        counts = joined_count(self.connection)
        self.assertEqual(counts["orders"], 7)
        self.assertEqual(counts["joined"], 4)
        self.assertEqual(
            counts["lost"],
            3,
            "nothing raised, the result is a perfectly good table, and a total "
            "computed from it is wrong",
        )

    def test_lost_is_the_difference(self):
        counts = joined_count(self.connection)
        self.assertEqual(counts["lost"], counts["orders"] - counts["joined"])

    def test_a_clean_join_loses_nothing(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE orders (order_id INTEGER, customer TEXT)")
        connection.execute("CREATE TABLE customers (email TEXT, country TEXT)")
        connection.execute("INSERT INTO orders VALUES (1, 'a@b.c')")
        connection.execute("INSERT INTO customers VALUES ('a@b.c', 'GB')")
        connection.commit()
        self.assertEqual(joined_count(connection)["lost"], 0)
        connection.close()


class TestUnmatched(Base):
    def setUp(self):
        super().setUp()
        self.rows = unmatched_orders(self.connection)
        self.by_id = {row["order_id"]: row for row in self.rows}

    def test_finds_every_unmatched_order(self):
        self.assertEqual(sorted(self.by_id), [1002, 1008, 1010])

    def test_is_sorted(self):
        self.assertEqual([row["order_id"] for row in self.rows], [1002, 1008, 1010])

    def test_a_blank_customer_is_missing(self):
        self.assertEqual(self.by_id[1008]["reason"], "missing")

    def test_a_spelling_difference_is_a_normalising_problem(self):
        self.assertEqual(
            self.by_id[1002]["reason"],
            "normalising",
            "the two systems agree and the strings do not, and the fix belongs "
            "at the coercion layer rather than in every query",
        )

    def test_a_real_value_that_matches_nothing_is_unknown(self):
        self.assertEqual(self.by_id[1010]["reason"], "unknown")

    def test_keeps_the_offending_value(self):
        self.assertEqual(self.by_id[1002]["customer"], " Grace@Example.com ")


class TestMultiplyingKeys(Base):
    def test_a_unique_reference_table_multiplies_nothing(self):
        self.assertEqual(multiplying_keys(self.connection), [])

    def test_finds_a_duplicated_reference_row(self):
        connection = seeded(CUSTOMERS + [("ada@example.com", "US")])
        self.assertEqual(
            multiplying_keys(connection),
            ["ada@example.com"],
            "every one of Ada's orders now comes out of the join twice, along "
            "with its total",
        )
        connection.close()

    def test_sorts_the_keys(self):
        extra = [("mei@example.com", "US"), ("ada@example.com", "US")]
        connection = seeded(CUSTOMERS + extra)
        self.assertEqual(
            multiplying_keys(connection), ["ada@example.com", "mei@example.com"]
        )
        connection.close()

    def test_a_duplicate_really_does_multiply_the_join(self):
        connection = seeded(CUSTOMERS + [("ada@example.com", "US")])
        before = joined_count(self.connection)["joined"]
        after = joined_count(connection)["joined"]
        self.assertGreater(after, before)
        connection.close()


class TestJoinIsSafe(Base):
    def test_reports_unsafe_when_rows_were_lost(self):
        report = join_is_safe(self.connection)
        self.assertEqual(report["lost"], 3)
        self.assertFalse(report["safe"])

    def test_reports_unsafe_when_the_join_multiplies(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE orders (order_id INTEGER, customer TEXT)")
        connection.execute("CREATE TABLE customers (email TEXT, country TEXT)")
        connection.execute("INSERT INTO orders VALUES (1, 'a@b.c')")
        connection.executemany(
            "INSERT INTO customers VALUES (?, ?)", [("a@b.c", "GB"), ("a@b.c", "US")]
        )
        connection.commit()

        report = join_is_safe(connection)
        self.assertEqual(report["lost"], -1, "the join produced more rows than it was given")
        self.assertEqual(report["multiplied"], ["a@b.c"])
        self.assertFalse(report["safe"])
        connection.close()

    def test_reports_safe_only_when_nothing_moved(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE orders (order_id INTEGER, customer TEXT)")
        connection.execute("CREATE TABLE customers (email TEXT, country TEXT)")
        connection.execute("INSERT INTO orders VALUES (1, 'a@b.c')")
        connection.execute("INSERT INTO customers VALUES ('a@b.c', 'GB')")
        connection.commit()

        report = join_is_safe(connection)
        self.assertTrue(report["safe"])
        self.assertEqual(report["lost"], 0)
        self.assertEqual(report["multiplied"], [])
        connection.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
