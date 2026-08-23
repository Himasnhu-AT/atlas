"""
Tests for: backfills.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import backfill, days_between, run_partition

CREATE_ORDERS = """
CREATE TABLE IF NOT EXISTS orders (
    order_id   INTEGER PRIMARY KEY,
    customer   TEXT NOT NULL,
    placed_at  TEXT NOT NULL,
    quantity   INTEGER,
    total      TEXT NOT NULL,
    status     TEXT NOT NULL
)
"""


def order(order_id: int, placed_at: str, total: str = "10.00") -> dict:
    return {
        "order_id": order_id,
        "customer": "a@example.com",
        "placed_at": placed_at,
        "quantity": 1,
        "total": total,
        "status": "shipped",
    }


SOURCE = {
    "2026-03-05": [order(1, "2026-03-05"), order(2, "2026-03-05")],
    "2026-03-06": [order(3, "2026-03-06")],
    "2026-03-07": [order(4, "2026-03-07"), order(5, "2026-03-07")],
}


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(CREATE_ORDERS)
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def snapshot(self):
        return sorted(
            tuple(row) for row in self.connection.execute("SELECT * FROM orders")
        )


class TestDaysBetween(unittest.TestCase):
    def test_is_inclusive_at_both_ends(self):
        self.assertEqual(
            days_between("2026-03-05", "2026-03-07"),
            ["2026-03-05", "2026-03-06", "2026-03-07"],
        )

    def test_one_day_is_one_day(self):
        self.assertEqual(days_between("2026-03-05", "2026-03-05"), ["2026-03-05"])

    def test_crosses_a_month_boundary(self):
        self.assertEqual(
            days_between("2026-02-27", "2026-03-02"),
            ["2026-02-27", "2026-02-28", "2026-03-01", "2026-03-02"],
        )

    def test_handles_a_leap_day(self):
        self.assertEqual(
            days_between("2024-02-28", "2024-03-01"),
            ["2024-02-28", "2024-02-29", "2024-03-01"],
        )

    def test_crosses_a_year_boundary(self):
        self.assertEqual(
            days_between("2025-12-31", "2026-01-01"), ["2025-12-31", "2026-01-01"]
        )

    def test_a_backwards_range_is_empty_not_an_error(self):
        self.assertEqual(days_between("2026-03-07", "2026-03-05"), [])


class TestRunPartition(Base):
    def test_writes_the_day(self):
        result = run_partition(self.connection, "2026-03-05", SOURCE["2026-03-05"])
        self.assertEqual(result, {"day": "2026-03-05", "deleted": 0, "written": 2})
        self.assertEqual(len(self.snapshot()), 2)

    def test_running_it_twice_changes_nothing(self):
        run_partition(self.connection, "2026-03-05", SOURCE["2026-03-05"])
        before = self.snapshot()
        run_partition(self.connection, "2026-03-05", SOURCE["2026-03-05"])
        self.assertEqual(self.snapshot(), before)

    def test_replaces_rather_than_accumulating(self):
        run_partition(self.connection, "2026-03-05", [order(1, "2026-03-05", "10.00")])
        result = run_partition(
            self.connection, "2026-03-05", [order(1, "2026-03-05", "99.00")]
        )
        self.assertEqual(result["deleted"], 1)
        rows = self.snapshot()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], "99.00", "a re-run repairs a partition loaded wrong")

    def test_an_empty_day_empties_the_partition(self):
        run_partition(self.connection, "2026-03-05", SOURCE["2026-03-05"])
        result = run_partition(self.connection, "2026-03-05", [])
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(
            self.snapshot(),
            [],
            "data that used to exist and should stop existing is the case most "
            "likely to be missed",
        )

    def test_does_not_touch_another_day(self):
        run_partition(self.connection, "2026-03-05", SOURCE["2026-03-05"])
        run_partition(self.connection, "2026-03-06", SOURCE["2026-03-06"])
        run_partition(self.connection, "2026-03-06", [])
        self.assertEqual(len(self.snapshot()), 2, "the 5th should be untouched")

    def test_ignores_rows_belonging_to_another_day(self):
        result = run_partition(
            self.connection, "2026-03-05", [order(1, "2026-03-05"), order(2, "2026-03-06")]
        )
        self.assertEqual(
            result["written"],
            1,
            "writing outside its partition is how a backfill corrupts a day "
            "nobody asked it to touch",
        )


class TestBackfill(Base):
    def test_runs_every_day_in_the_range(self):
        report = backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        self.assertEqual(report["days"], 3)
        self.assertEqual(report["written"], 5)
        self.assertEqual(len(self.snapshot()), 5)

    def test_reports_per_day_in_order(self):
        report = backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        self.assertEqual(
            [entry["day"] for entry in report["per_day"]],
            ["2026-03-05", "2026-03-06", "2026-03-07"],
        )
        self.assertEqual(report["per_day"][1]["written"], 1)

    def test_running_it_twice_leaves_the_table_identical(self):
        backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        before = self.snapshot()
        backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        self.assertEqual(
            self.snapshot(),
            before,
            "a backfill is the daily run in a loop, and has to be as re-runnable",
        )

    def test_a_day_with_no_source_rows_is_emptied(self):
        backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        thinner = {day: rows for day, rows in SOURCE.items() if day != "2026-03-06"}
        report = backfill(self.connection, "2026-03-05", "2026-03-07", thinner)
        self.assertEqual(report["deleted"], 5)
        self.assertEqual(len(self.snapshot()), 4)

    def test_days_outside_the_range_are_untouched(self):
        backfill(self.connection, "2026-03-05", "2026-03-07", SOURCE)
        backfill(self.connection, "2026-03-06", "2026-03-06", {})
        remaining = {row[2] for row in self.snapshot()}
        self.assertEqual(remaining, {"2026-03-05", "2026-03-07"})

    def test_an_empty_range_does_nothing(self):
        report = backfill(self.connection, "2026-03-07", "2026-03-05", SOURCE)
        self.assertEqual(report["days"], 0)
        self.assertEqual(report["per_day"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
