"""
Tests for: freshness.

Run with `python3 test.py`.
"""

from __future__ import annotations

import sqlite3
import unittest

from solution import (
    age_in_hours,
    business_hours_between,
    freshness_verdict,
    is_stale,
    newest_row,
)

# 2026-03-06 is a Friday, 2026-03-07 a Saturday, 2026-03-09 a Monday.
FRIDAY_NOON = "2026-03-06T12:00:00Z"
MONDAY_NOON = "2026-03-09T12:00:00Z"


def seeded(timestamps) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE orders (order_id INTEGER, placed_at TEXT)")
    connection.executemany(
        "INSERT INTO orders VALUES (?, ?)", list(enumerate(timestamps, start=1))
    )
    connection.commit()
    return connection


class TestNewestRow(unittest.TestCase):
    def test_finds_the_most_recent(self):
        connection = seeded(["2026-03-04", "2026-03-06", "2026-03-05"])
        self.assertEqual(newest_row(connection), "2026-03-06")

    def test_an_empty_table_has_none(self):
        self.assertIsNone(
            newest_row(seeded([])),
            "an empty table is a different alarm from a stale one",
        )


class TestAgeInHours(unittest.TestCase):
    def test_measures_hours(self):
        self.assertAlmostEqual(
            age_in_hours("2026-03-06T06:00:00Z", FRIDAY_NOON), 6.0
        )

    def test_reads_a_bare_date_as_the_start_of_the_day(self):
        self.assertAlmostEqual(
            age_in_hours("2026-03-06", FRIDAY_NOON),
            12.0,
            "the conservative reading: a freshness check should never round "
            "towards 'probably fine'",
        )

    def test_none_has_no_age(self):
        self.assertIsNone(age_in_hours(None, FRIDAY_NOON))

    def test_a_future_timestamp_is_negative(self):
        age = age_in_hours("2026-03-06T18:00:00Z", FRIDAY_NOON)
        self.assertLess(
            age, 0, "clock skew is real, and clamping it hides the thing worth knowing"
        )


class TestIsStale(unittest.TestCase):
    def test_recent_data_is_not_stale(self):
        self.assertFalse(is_stale("2026-03-06T11:00:00Z", FRIDAY_NOON, 24))

    def test_old_data_is_stale(self):
        self.assertTrue(is_stale("2026-03-01T11:00:00Z", FRIDAY_NOON, 24))

    def test_exactly_at_the_limit_is_not_stale(self):
        self.assertFalse(is_stale("2026-03-05T12:00:00Z", FRIDAY_NOON, 24))

    def test_no_data_is_stale(self):
        self.assertTrue(
            is_stale(None, FRIDAY_NOON, 24),
            "the alternative is treating 'no data at all' as fresh",
        )


class TestBusinessHours(unittest.TestCase):
    def test_counts_a_plain_weekday_gap(self):
        self.assertAlmostEqual(
            business_hours_between("2026-03-06T06:00:00Z", FRIDAY_NOON), 6.0
        )

    def test_skips_the_weekend(self):
        # Friday noon to Monday noon is 72 wall hours and 24 business hours:
        # twelve on Friday afternoon and twelve on Monday morning.
        self.assertAlmostEqual(
            business_hours_between(FRIDAY_NOON, MONDAY_NOON),
            24.0,
            "the most common false alarm here is a Monday morning page for a "
            "feed that has never run at the weekend",
        )

    def test_a_whole_weekend_counts_nothing(self):
        self.assertAlmostEqual(
            business_hours_between("2026-03-07T00:00:00Z", "2026-03-09T00:00:00Z"), 0.0
        )

    def test_an_end_before_the_start_is_zero(self):
        self.assertEqual(business_hours_between(MONDAY_NOON, FRIDAY_NOON), 0.0)

    def test_the_same_instant_is_zero(self):
        self.assertEqual(business_hours_between(FRIDAY_NOON, FRIDAY_NOON), 0.0)

    def test_handles_a_partial_hour(self):
        self.assertAlmostEqual(
            business_hours_between("2026-03-06T12:00:00Z", "2026-03-06T12:30:00Z"), 0.5
        )


class TestVerdict(unittest.TestCase):
    def test_everything_fine(self):
        verdict = freshness_verdict(
            "2026-03-06T11:00:00Z", "2026-03-06T10:00:00Z", FRIDAY_NOON, 24, 24
        )
        self.assertEqual(verdict["state"], "fresh")
        self.assertTrue(verdict["ran_recently"])
        self.assertTrue(verdict["data_fresh"])

    def test_the_job_ran_and_the_source_stopped(self):
        verdict = freshness_verdict(
            "2026-03-06T11:00:00Z", "2026-03-01T10:00:00Z", FRIDAY_NOON, 24, 24
        )
        self.assertEqual(
            verdict["state"],
            "source_stopped",
            "the pipeline is fine and the source is not, which is a different "
            "person from the one 'stale' would send you to",
        )

    def test_the_job_stopped_and_the_data_has_not_aged_out_yet(self):
        verdict = freshness_verdict(
            "2026-03-01T11:00:00Z", "2026-03-06T10:00:00Z", FRIDAY_NOON, 24, 48
        )
        self.assertEqual(verdict["state"], "not_running")

    def test_both_stopped(self):
        verdict = freshness_verdict(
            "2026-02-01T11:00:00Z", "2026-02-01T10:00:00Z", FRIDAY_NOON, 24, 24
        )
        self.assertEqual(verdict["state"], "stalled")

    def test_a_job_that_never_ran_is_not_running(self):
        verdict = freshness_verdict(None, "2026-03-06T10:00:00Z", FRIDAY_NOON, 24, 24)
        self.assertEqual(verdict["state"], "not_running")
        self.assertIsNone(verdict["run_age_hours"])

    def test_an_empty_table_with_a_healthy_job_is_source_stopped(self):
        verdict = freshness_verdict("2026-03-06T11:00:00Z", None, FRIDAY_NOON, 24, 24)
        self.assertEqual(verdict["state"], "source_stopped")
        self.assertIsNone(verdict["data_age_hours"])

    def test_reports_both_ages(self):
        verdict = freshness_verdict(
            "2026-03-06T11:00:00Z", "2026-03-06T06:00:00Z", FRIDAY_NOON, 24, 24
        )
        self.assertAlmostEqual(verdict["run_age_hours"], 1.0)
        self.assertAlmostEqual(verdict["data_age_hours"], 6.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
