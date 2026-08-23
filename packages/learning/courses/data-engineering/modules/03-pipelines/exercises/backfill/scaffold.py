"""
Backfills.

Re-running a pipeline over the past is the same operation as running it over
today, and if it is not, one of the two is wrong.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3


def days_between(start: str, end: str) -> list[str]:
    """
    Every day from start to end, inclusive.

    Args:
        start: "YYYY-MM-DD".
        end: "YYYY-MM-DD".

    Returns:
        The days in order, inclusive at both ends. A start after the end gives
        [] rather than raising: a backfill over an empty range is a no-op, not
        an error, and raising here turns a harmless argument into a page at 2am.

        Use `datetime.date` and `timedelta` rather than string arithmetic. Month
        and year boundaries are where a hand-rolled version goes wrong, and this
        function has to be right about them.
    """
    raise NotImplementedError


def run_partition(connection: sqlite3.Connection, day: str, rows: list[dict]) -> dict:
    """
    Load one day, replacing whatever was there.

    Delete the day's existing rows and insert the new ones, in ONE transaction.
    Delete-then-insert is idempotent by construction: the state after any number
    of runs is the state after one, and it repairs a partition that was
    previously loaded wrong.

    Args:
        connection: an open connection holding `orders`.
        day: the partition, matching `placed_at`.
        rows: every row belonging to that day. Rows whose `placed_at` is some
            other day are ignored rather than written: a run owns one partition
            and writing outside it is how a backfill corrupts a day nobody asked
            it to touch.

    Returns:
        A dict shaped:

            {"day": "2026-03-06", "deleted": 2, "written": 3}

        A day whose new input is empty deletes its old rows and writes nothing.
        That is a real result and has to be possible: data that used to exist
        and should stop existing is the case most likely to be missed, because
        it never comes up while the pipeline is working.
    """
    raise NotImplementedError


def backfill(connection: sqlite3.Connection, start: str, end: str, source: dict) -> dict:
    """
    Run a range of partitions and report per day.

    Args:
        connection: an open connection.
        start: first day, inclusive.
        end: last day, inclusive.
        source: maps a day to the rows belonging to it. A day missing from this
            dict has no rows, which is different from a day that is not in the
            range: the first should be emptied, the second should be untouched.

    Returns:
        A dict shaped:

            {
                "days": 3,
                "written": 7,
                "deleted": 2,
                "per_day": [{"day": "...", "deleted": 0, "written": 3}, ...],
            }

        `per_day` is in order. "It worked" is not a useful report on a
        thirty-day backfill; a list of days with row counts is, because it is
        the only way to notice that one day in the middle produced nothing.
    """
    raise NotImplementedError
