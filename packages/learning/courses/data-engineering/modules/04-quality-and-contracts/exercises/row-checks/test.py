"""
Tests for: counting is a test.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import (
    check_allowed_values,
    check_no_nulls,
    check_row_count,
    check_sum_in_range,
    check_unique,
    run_checks,
)

STATUSES = {"shipped", "pending", "cancelled", "refunded", "returned"}


def seeded(rows) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE orders (
            order_id  INTEGER,
            customer  TEXT,
            placed_at TEXT,
            total     TEXT,
            status    TEXT
        )
        """
    )
    connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", rows)
    connection.commit()
    return connection


GOOD = [
    (1, "a@b.c", "2026-03-05", "10.00", "shipped"),
    (2, "d@e.f", "2026-03-05", "20.00", "pending"),
    (3, "g@h.i", "2026-03-06", "30.00", "shipped"),
]


class TestRowCount(unittest.TestCase):
    def test_passes_in_line_with_history(self):
        connection = seeded(GOOD)
        result = check_row_count(connection, [3, 3, 4])
        self.assertTrue(result["passed"])
        self.assertEqual(result["name"], "row_count")

    def test_fails_on_a_truncated_extract(self):
        connection = seeded(GOOD[:1])
        result = check_row_count(connection, [100, 98, 102])
        self.assertFalse(
            result["passed"],
            "the extract was empty or truncated is the most common failure there is",
        )

    def test_uses_the_median_so_one_bad_day_does_not_move_the_bar(self):
        connection = seeded(GOOD)
        # A mean of [3, 3, 3, 3000] is 752 and would fail; the median is 3.
        self.assertTrue(check_row_count(connection, [3, 3, 3, 3000])["passed"])

    def test_passes_with_no_history(self):
        connection = seeded(GOOD)
        result = check_row_count(connection, [])
        self.assertTrue(
            result["passed"],
            "a check that fails on a first run trains people to ignore it",
        )
        self.assertIn("no history", result["detail"])

    def test_says_what_it_saw(self):
        connection = seeded(GOOD)
        self.assertIn("3", check_row_count(connection, [3])["detail"])


class TestNoNulls(unittest.TestCase):
    def test_passes_when_there_are_none(self):
        connection = seeded(GOOD)
        self.assertTrue(check_no_nulls(connection, ["order_id", "customer"])["passed"])

    def test_fails_and_names_the_column(self):
        connection = seeded(GOOD + [(4, None, "2026-03-06", "5.00", "shipped")])
        result = check_no_nulls(connection, ["order_id", "customer"])
        self.assertFalse(result["passed"])
        self.assertIn(
            "customer",
            result["detail"],
            "'nulls found' sends somebody looking through six columns",
        )

    def test_refuses_a_column_it_cannot_vouch_for(self):
        connection = seeded(GOOD)
        with self.assertRaises(ValueError):
            check_no_nulls(connection, ["order_id; DROP TABLE orders"])


class TestUnique(unittest.TestCase):
    def test_passes_when_unique(self):
        self.assertTrue(check_unique(seeded(GOOD))["passed"])

    def test_fails_and_names_the_duplicate(self):
        connection = seeded(GOOD + [(1, "z@z.z", "2026-03-07", "5.00", "shipped")])
        result = check_unique(connection)
        self.assertFalse(result["passed"])
        self.assertIn("1", result["detail"])

    def test_counts_rather_than_listing_when_there_are_many(self):
        # Ten distinct ids, each appearing four times. A check that prints four
        # thousand ids is a check nobody reads.
        rows = [(n % 10, "a@b.c", "2026-03-05", "1.00", "shipped") for n in range(40)]
        result = check_unique(seeded(rows))
        self.assertFalse(result["passed"])
        self.assertIn("10", result["detail"])
        self.assertNotIn("repeated: ", result["detail"])

    def test_refuses_an_unknown_column(self):
        with self.assertRaises(ValueError):
            check_unique(seeded(GOOD), "nope")


class TestAllowedValues(unittest.TestCase):
    def test_passes_when_every_value_is_known(self):
        self.assertTrue(check_allowed_values(seeded(GOOD), "status", STATUSES)["passed"])

    def test_fails_on_a_new_state(self):
        connection = seeded(GOOD + [(4, "a@b.c", "2026-03-06", "5.00", "disputed")])
        result = check_allowed_values(connection, "status", STATUSES)
        self.assertFalse(result["passed"])
        self.assertIn("disputed", result["detail"])

    def test_a_null_is_not_an_unexpected_value(self):
        connection = seeded(GOOD + [(4, "a@b.c", "2026-03-06", "5.00", None)])
        self.assertTrue(
            check_allowed_values(connection, "status", STATUSES)["passed"],
            "nulls are check_no_nulls's business, and reporting them twice is noise",
        )


class TestSumInRange(unittest.TestCase):
    def test_passes_in_line_with_history(self):
        connection = seeded(GOOD)
        self.assertTrue(check_sum_in_range(connection, "total", [60.0, 58.0, 62.0])["passed"])

    def test_fails_when_a_join_doubled_it(self):
        connection = seeded(GOOD + GOOD)
        result = check_sum_in_range(connection, "total", [60.0, 58.0, 62.0])
        self.assertFalse(
            result["passed"],
            "the double-counting join produces a number that looks plausible",
        )

    def test_skips_values_it_cannot_read(self):
        connection = seeded(GOOD + [(4, "a@b.c", "2026-03-06", "n/a", "shipped")])
        result = check_sum_in_range(connection, "total", [60.0])
        self.assertTrue(result["passed"])
        self.assertIn("unreadable", result["detail"])

    def test_passes_with_no_history(self):
        self.assertTrue(check_sum_in_range(seeded(GOOD), "total", [])["passed"])


class TestRunChecks(unittest.TestCase):
    def test_passes_when_everything_passed(self):
        results = [
            {"name": "a", "passed": True, "detail": ""},
            {"name": "b", "passed": True, "detail": ""},
        ]
        verdict = run_checks(results)
        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["failed"], [])

    def test_reports_every_failure_not_just_the_first(self):
        results = [
            {"name": "a", "passed": False, "detail": ""},
            {"name": "b", "passed": True, "detail": ""},
            {"name": "c", "passed": False, "detail": ""},
        ]
        verdict = run_checks(results)
        self.assertFalse(verdict["passed"])
        self.assertEqual(
            verdict["failed"],
            ["a", "c"],
            'the answer to "is today usable" is never "check three failed"',
        )

    def test_keeps_every_result(self):
        results = [{"name": "a", "passed": False, "detail": "why"}]
        self.assertEqual(run_checks(results)["results"], results)

    def test_no_checks_is_a_pass(self):
        self.assertTrue(run_checks([])["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
