"""
Tests for: the partial run.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import (
    claim_partition,
    create_schema,
    finish_partition,
    partitions_to_run,
    run_range,
)

DAYS = ["2026-03-05", "2026-03-06", "2026-03-07", "2026-03-08"]


def clock():
    """A predictable clock, so a test never depends on wall time."""
    ticks = iter(f"2026-03-09T00:00:{n:02d}Z" for n in range(60))
    return lambda: next(ticks)


class Base(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        create_schema(self.connection)
        self.now = clock()

    def tearDown(self):
        self.connection.close()

    def status(self, partition: str):
        row = self.connection.execute(
            "SELECT status FROM run_log WHERE partition = ?", (partition,)
        ).fetchone()
        return row[0] if row else None


class TestClaim(Base):
    def test_claims_an_unclaimed_partition(self):
        self.assertTrue(claim_partition(self.connection, DAYS[0], self.now()))
        self.assertEqual(self.status(DAYS[0]), "running")

    def test_a_second_claim_is_refused(self):
        claim_partition(self.connection, DAYS[0], self.now())
        self.assertFalse(
            claim_partition(self.connection, DAYS[0], self.now()),
            "two copies of the same backfill running at once is a real hazard",
        )

    def test_different_partitions_are_independent(self):
        self.assertTrue(claim_partition(self.connection, DAYS[0], self.now()))
        self.assertTrue(claim_partition(self.connection, DAYS[1], self.now()))


class TestFinish(Base):
    def test_marks_success(self):
        claim_partition(self.connection, DAYS[0], self.now())
        finish_partition(self.connection, DAYS[0], self.now(), rows_written=7)
        self.assertEqual(self.status(DAYS[0]), "done")

        row = self.connection.execute(
            "SELECT rows_written, finished_at, error FROM run_log WHERE partition = ?",
            (DAYS[0],),
        ).fetchone()
        self.assertEqual(row[0], 7)
        self.assertIsNotNone(row[1])
        self.assertIsNone(row[2])

    def test_marks_failure_with_the_reason(self):
        claim_partition(self.connection, DAYS[0], self.now())
        finish_partition(self.connection, DAYS[0], self.now(), error="source unreachable")
        self.assertEqual(self.status(DAYS[0]), "failed")

        error = self.connection.execute(
            "SELECT error FROM run_log WHERE partition = ?", (DAYS[0],)
        ).fetchone()[0]
        self.assertEqual(error, "source unreachable")


class TestPartitionsToRun(Base):
    def test_everything_is_outstanding_at_first(self):
        self.assertEqual(partitions_to_run(self.connection, DAYS), DAYS)

    def test_a_done_partition_is_skipped(self):
        claim_partition(self.connection, DAYS[0], self.now())
        finish_partition(self.connection, DAYS[0], self.now(), rows_written=1)
        self.assertEqual(partitions_to_run(self.connection, DAYS), DAYS[1:])

    def test_an_interrupted_partition_is_still_outstanding(self):
        claim_partition(self.connection, DAYS[0], self.now())
        self.assertIn(
            DAYS[0],
            partitions_to_run(self.connection, DAYS),
            "it may have written some rows and may not have finished, which is "
            "exactly why the write has to be idempotent",
        )

    def test_a_failed_partition_is_retried(self):
        claim_partition(self.connection, DAYS[0], self.now())
        finish_partition(self.connection, DAYS[0], self.now(), error="boom")
        self.assertIn(DAYS[0], partitions_to_run(self.connection, DAYS))

    def test_keeps_the_given_order(self):
        self.assertEqual(partitions_to_run(self.connection, DAYS), DAYS)


class TestRunRange(Base):
    def test_runs_everything_and_reports(self):
        report = run_range(self.connection, DAYS, lambda day: 3, self.now)
        self.assertEqual(report["done"], DAYS)
        self.assertEqual(report["failed"], [])
        self.assertEqual(report["skipped"], [])
        self.assertFalse(report["stopped_early"])

    def test_carries_on_past_one_failure(self):
        def work(day):
            if day == DAYS[1]:
                raise RuntimeError("bad day")
            return 1

        report = run_range(self.connection, DAYS, work, self.now)
        self.assertEqual(report["done"], [DAYS[0], DAYS[2], DAYS[3]])
        self.assertEqual(len(report["failed"]), 1)
        self.assertEqual(
            report["failed"][0],
            {"partition": DAYS[1], "error": "bad day"},
            "one bad day should not hide the fact that the others were fine",
        )

    def test_stops_after_enough_consecutive_failures(self):
        def work(day):
            raise RuntimeError("everything is down")

        report = run_range(self.connection, DAYS, work, self.now, max_consecutive_failures=2)
        self.assertTrue(report["stopped_early"])
        self.assertEqual(len(report["failed"]), 2)
        self.assertEqual(self.status(DAYS[2]), None, "it never got that far")

    def test_a_success_resets_the_failure_run(self):
        seen: list[str] = []

        def work(day):
            seen.append(day)
            if day in (DAYS[0], DAYS[2]):
                raise RuntimeError("intermittent")
            return 1

        report = run_range(self.connection, DAYS, work, self.now, max_consecutive_failures=2)
        self.assertFalse(report["stopped_early"], "the failures were not consecutive")
        self.assertEqual(seen, DAYS)

    def test_a_resume_skips_what_was_done_and_says_so(self):
        first = run_range(self.connection, DAYS[:2], lambda day: 2, self.now)
        self.assertEqual(first["done"], DAYS[:2])

        second = run_range(self.connection, DAYS, lambda day: 2, self.now)
        self.assertEqual(
            second["skipped"],
            DAYS[:2],
            "a resume that silently does less is indistinguishable from one "
            "that silently did nothing",
        )
        self.assertEqual(second["done"], DAYS[2:])

    def test_resuming_after_an_interruption_redoes_that_partition(self):
        # A crash leaves the partition claimed and unfinished.
        claim_partition(self.connection, DAYS[1], self.now())

        seen: list[str] = []
        run_range(self.connection, DAYS, lambda day: seen.append(day) or 1, self.now)
        self.assertIn(DAYS[1], seen)
        self.assertEqual(self.status(DAYS[1]), "done")

    def test_running_it_again_after_success_does_nothing(self):
        run_range(self.connection, DAYS, lambda day: 1, self.now)
        again = run_range(self.connection, DAYS, lambda day: 1, self.now)
        self.assertEqual(again["done"], [])
        self.assertEqual(again["skipped"], DAYS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
