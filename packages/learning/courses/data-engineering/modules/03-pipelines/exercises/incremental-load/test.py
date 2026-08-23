"""
Tests for: watermarks.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import create_schema, load_increment, read_watermark, rows_to_process

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


def order(order_id: int, placed_at: str, status: str = "shipped") -> dict:
    return {
        "order_id": order_id,
        "customer": "a@example.com",
        "placed_at": placed_at,
        "quantity": 1,
        "total": "10.00",
        "status": status,
    }


DAY_ONE = [order(1, "2026-03-05"), order(2, "2026-03-06"), order(3, "2026-03-06")]
DAY_TWO = [order(4, "2026-03-06"), order(5, "2026-03-07")]


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(CREATE_ORDERS)
        create_schema(self.connection)
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def orders(self):
        return sorted(
            tuple(row) for row in self.connection.execute("SELECT * FROM orders")
        )


class TestWatermarkStorage(Base):
    def test_an_unloaded_source_has_no_watermark(self):
        self.assertIsNone(
            read_watermark(self.connection, "orders"),
            "None means load everything, which is right for a first run",
        )

    def test_reads_back_what_was_written(self):
        load_increment(self.connection, DAY_ONE)
        self.assertEqual(read_watermark(self.connection, "orders"), "2026-03-06")

    def test_watermarks_are_named_separately(self):
        load_increment(self.connection, DAY_ONE, name="orders")
        self.assertIsNone(read_watermark(self.connection, "refunds"))


class TestRowsToProcess(unittest.TestCase):
    def test_a_first_run_takes_everything(self):
        self.assertEqual(len(rows_to_process(DAY_ONE, None)), 3)

    def test_uses_a_closed_boundary(self):
        selected = rows_to_process(DAY_ONE + DAY_TWO, "2026-03-06")
        ids = {row["order_id"] for row in selected}
        self.assertIn(
            2,
            ids,
            "a strict > skips a row sharing the boundary timestamp, and no "
            "later run ever picks it up",
        )
        self.assertIn(4, ids)
        self.assertNotIn(1, ids)

    def test_keeps_the_original_order(self):
        selected = rows_to_process(DAY_ONE, None)
        self.assertEqual([row["order_id"] for row in selected], [1, 2, 3])

    def test_skips_rows_with_no_timestamp(self):
        rows = DAY_ONE + [{"order_id": 99}]
        self.assertEqual(len(rows_to_process(rows, None)), 3)

    def test_nothing_after_the_watermark_is_nothing(self):
        self.assertEqual(rows_to_process(DAY_ONE, "2026-04-01"), [])


class TestLoadIncrement(Base):
    def test_writes_the_rows_and_moves_the_mark(self):
        report = load_increment(self.connection, DAY_ONE)
        self.assertEqual(report["written"], 3)
        self.assertEqual(report["watermark"], "2026-03-06")
        self.assertEqual(len(self.orders()), 3)

    def test_running_the_same_input_twice_changes_nothing(self):
        load_increment(self.connection, DAY_ONE)
        before = self.orders()
        mark_before = read_watermark(self.connection, "orders")

        load_increment(self.connection, DAY_ONE)
        self.assertEqual(
            self.orders(),
            before,
            "the state after N runs of the same input has to match the state "
            "after one",
        )
        self.assertEqual(read_watermark(self.connection, "orders"), mark_before)

    def test_the_boundary_row_is_not_lost_across_runs(self):
        load_increment(self.connection, DAY_ONE)
        mark = read_watermark(self.connection, "orders")

        second = rows_to_process(DAY_ONE + DAY_TWO, mark)
        load_increment(self.connection, second)

        ids = {row[0] for row in self.orders()}
        self.assertEqual(
            ids, {1, 2, 3, 4, 5}, "every order should be present after two runs"
        )

    def test_an_upsert_corrects_rather_than_duplicating(self):
        load_increment(self.connection, [order(1, "2026-03-05", status="pending")])
        load_increment(self.connection, [order(1, "2026-03-05", status="shipped")])

        rows = self.orders()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][5], "shipped")

    def test_an_empty_run_does_not_move_the_mark(self):
        load_increment(self.connection, DAY_ONE)
        report = load_increment(self.connection, [])
        self.assertEqual(report["written"], 0)
        self.assertEqual(
            report["watermark"],
            "2026-03-06",
            "an empty run is not evidence that time has passed",
        )

    def test_the_mark_never_goes_backwards(self):
        load_increment(self.connection, DAY_TWO)
        load_increment(self.connection, [order(9, "2026-03-01")])
        self.assertEqual(read_watermark(self.connection, "orders"), "2026-03-07")

    def test_a_failed_write_leaves_the_mark_where_it_was(self):
        load_increment(self.connection, DAY_ONE)
        mark_before = read_watermark(self.connection, "orders")

        broken = [order(10, "2026-03-09"), {"order_id": 11, "placed_at": "2026-03-09"}]
        with self.assertRaises(Exception):
            load_increment(self.connection, broken)

        self.assertEqual(
            read_watermark(self.connection, "orders"),
            mark_before,
            "a mark ahead of the data means no later run goes back for those rows",
        )
        self.assertEqual(len(self.orders()), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
