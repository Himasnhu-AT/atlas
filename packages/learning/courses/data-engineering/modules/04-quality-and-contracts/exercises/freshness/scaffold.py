"""
Freshness.

A pipeline that runs successfully and loads nothing looks exactly like one that
runs successfully. This is the check that tells them apart, and it is the one
most often missing.

Nothing here reads the clock. `now` is always passed in, because a check that
depends on wall time cannot be tested and a check that cannot be tested is a
check nobody trusts.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3


def newest_row(connection: sqlite3.Connection, column: str = "placed_at") -> str | None:
    """
    The timestamp of the most recent row.

    Args:
        connection: an open connection holding `orders`.
        column: the timestamp column.

    Returns:
        The maximum value, or None when the table is empty.

        An empty table is not fresh and it is not stale either: it is a
        different alarm, and conflating the two sends somebody to look at a
        source that is working.
    """
    raise NotImplementedError


def age_in_hours(timestamp: str | None, now: str) -> float | None:
    """
    How old a timestamp is, in hours.

    Args:
        timestamp: ISO 8601, either a date or a full timestamp. A bare date is
            treated as midnight at the start of that day, which is the
            conservative reading: it makes the data look older rather than
            newer, and a freshness check should never round in the direction of
            "probably fine".
        now: ISO 8601 timestamp to measure against.

        Parse `Z` as UTC and then compare naive values, because every timestamp
        in this course represents UTC.

    Returns:
        Hours, as a float. None when `timestamp` is None.

        A timestamp in the future gives a negative number rather than zero or an
        error. Clock skew between a source and here is real, and a check that
        silently clamps it hides the thing worth knowing.
    """
    raise NotImplementedError


def is_stale(timestamp: str | None, now: str, max_age_hours: float) -> bool:
    """
    Is the data older than the cadence allows?

    Args:
        timestamp: the newest row's timestamp, or None.
        now: ISO 8601.
        max_age_hours: how old the newest row may be. This has to come from how
            the source actually delivers. An hourly feed is stale after two
            hours; a nightly batch at 2am is fine at 11pm with data from
            twenty-two hours ago.

    Returns:
        True when the data is too old. None (an empty table) is stale, because
        the alternative is treating "no data at all" as fresh.
    """
    raise NotImplementedError


def business_hours_between(start: str, end: str) -> float:
    """
    Hours between two timestamps, counting weekdays only.

    The most common false alarm in this whole area is a Monday morning page for
    a feed that has never run at the weekend. Measuring in business hours makes
    that feed healthy on Monday and still catches it if it stops on Wednesday.

    Args:
        start: ISO 8601.
        end: ISO 8601.

    Returns:
        Hours, excluding any part falling on a Saturday or Sunday. Zero when
        `end` is at or before `start`.

        Whole weekend days contribute nothing. A partial weekday counts only its
        part. Working this out hour by hour is fine and is much easier to get
        right than a closed form.
    """
    raise NotImplementedError


def freshness_verdict(
    last_run: str | None,
    newest: str | None,
    now: str,
    max_run_age_hours: float,
    max_data_age_hours: float,
) -> dict:
    """
    One verdict naming which failure this is.

    Between the job's last run and the data's age there are four cases, and only
    one is good. The other three want three different people, which is why the
    verdict says which rather than just "stale".

    Args:
        last_run: when the job last completed, or None if it never has.
        newest: the newest row's timestamp, or None.
        now: ISO 8601.
        max_run_age_hours: how long since the job ran before that is wrong.
        max_data_age_hours: how old the data may be.

    Returns:
        A dict shaped:

            {
                "state": "source_stopped",
                "ran_recently": True,
                "data_fresh": False,
                "run_age_hours": 1.0,
                "data_age_hours": 96.0,
            }

        `state` is one of:

          - "fresh"           the job ran and the data is current
          - "source_stopped"  the job ran and the data is not current, so the
                              pipeline is fine and the source is not
          - "not_running"     the job has not run and the data is still current,
                              so the scheduler is broken and nobody has noticed
                              yet
          - "stalled"         neither, which usually means the scheduler broke a
                              while ago

        "Stale" on its own sends somebody to the wrong place half the time.
    """
    raise NotImplementedError
