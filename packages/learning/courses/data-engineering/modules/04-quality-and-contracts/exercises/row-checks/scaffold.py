"""
Counting is a test.

Five boring checks that between them catch most real incidents, and a runner
that reports all of them rather than stopping at the first failure.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3


def check_row_count(connection: sqlite3.Connection, history: list[int], tolerance: float = 0.5) -> dict:
    """
    Is today's row count in line with recent runs?

    This single check catches more real incidents than everything else
    combined, because "the extract was empty or truncated" is by far the most
    common failure.

    Args:
        connection: an open connection holding `orders`.
        history: row counts from recent runs, oldest first. May be empty on a
            first run.
        tolerance: how far from the median is acceptable, as a fraction. 0.5
            means "within 50% either way".

    Returns:
        A dict shaped:

            {"name": "row_count", "passed": True, "detail": "..."}

        Compare against the MEDIAN of history, not the mean and not a fixed
        number. A relative threshold survives growth, seasonality and the day
        somebody runs a campaign; "at least 9,000 rows" is stale within a
        quarter and wrong every December. The median rather than the mean
        because one bad day in the history should not move the bar.

        With no history, pass: there is nothing to compare against, and a check
        that fails on a first run trains people to ignore it. Say so in
        `detail`.
    """
    raise NotImplementedError


def check_no_nulls(connection: sqlite3.Connection, columns: list[str]) -> dict:
    """
    Are the columns that can never be null actually never null?

    A null appearing here means a constraint is missing or a load path is
    bypassing it.

    Args:
        connection: an open connection.
        columns: column names that must never be null.

    Returns:
        {"name": "no_nulls", "passed": bool, "detail": str}

        `detail` names which columns had nulls and how many, because "nulls
        found" sends somebody looking through six columns.

        Column names cannot be parameterised. Validate them against the table's
        real columns rather than interpolating what you were given.
    """
    raise NotImplementedError


def check_unique(connection: sqlite3.Connection, column: str = "order_id") -> dict:
    """
    Is the column that everything assumes is unique actually unique?

    Every downstream sum depends on this, and it is the whole subject of the
    two modules before this one.

    Returns:
        {"name": "unique", "passed": bool, "detail": str}

        `detail` names the offending values when there are few enough to be
        useful, and says how many there are when there are not. A check that
        prints four thousand ids is a check nobody reads.
    """
    raise NotImplementedError


def check_allowed_values(connection: sqlite3.Connection, column: str, allowed: set) -> dict:
    """
    Are the values in a column ones you know about?

    A sixth status appearing is the source adding a state nobody told you
    about. That is a normal event, and one you want to hear about on the day
    rather than when somebody asks why the funnel does not add up.

    Returns:
        {"name": "allowed_values", "passed": bool, "detail": str}

        Nulls are not unexpected values and are `check_no_nulls`'s business.
        Skip them here rather than reporting the same problem twice.
    """
    raise NotImplementedError


def check_sum_in_range(
    connection: sqlite3.Connection,
    column: str,
    history: list[float],
    tolerance: float = 0.5,
) -> dict:
    """
    Is a total in line with recent runs?

    Catches the double-counting join and the truncated extract at once, which
    are the two failures most likely to look like a plausible number.

    Args:
        connection: an open connection.
        column: a numeric column, stored as text. Money is stored exactly, so
            read it as a Decimal rather than a float.
        history: recent totals, oldest first.
        tolerance: as above.

    Returns:
        {"name": "sum_in_range", "passed": bool, "detail": str}

        Values that will not parse are skipped rather than counted as zero, and
        said so in `detail`. A value nobody can read is not evidence the value
        was nothing. Nulls are also skipped: `check_no_nulls` owns that alarm.

        Validate the column against the table's real columns before interpolating
        it into SQL.
    """
    raise NotImplementedError


def run_checks(checks: list[dict]) -> dict:
    """
    Gather results into one verdict.

    Args:
        checks: the outputs of the checks above.

    Returns:
        A dict shaped:

            {"passed": False, "failed": ["unique"], "results": [...]}

        Every check runs and every result is reported. Somebody is about to ask
        "is today's data usable", and the answer to that is never "check three
        failed". `failed` is in the order the checks were given.
    """
    raise NotImplementedError
