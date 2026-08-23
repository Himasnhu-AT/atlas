"""
The partial run.

Everything so far assumed the job finished. A run that cannot say what it
completed cannot be resumed, and a backfill that has to start over is a gamble
that gets worse as the range gets longer.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3

CREATE_RUN_LOG = """
CREATE TABLE IF NOT EXISTS run_log (
    partition    TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    rows_written INTEGER,
    error        TEXT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
)
"""


def create_schema(connection: sqlite3.Connection) -> None:
    """
    Create the run log.

    In a table, not in memory and not in the log file. Resuming needs a durable
    answer to "what is left", and that is the only question a resume asks.
    """
    raise NotImplementedError


def claim_partition(connection: sqlite3.Connection, partition: str, now: str) -> bool:
    """
    Take ownership of a partition, if nobody else has it.

    Insert a row with status 'running'. The primary key does the work: if the
    insert conflicts, somebody else got there first.

    This is not a distributed lock and will not save you from every
    interleaving. It turns the common case — somebody starting the backfill
    again because they thought the first had died — from silent double
    processing into a row that says who got there first.

    Args:
        connection: an open connection.
        partition: the day being claimed.
        now: ISO timestamp for `started_at`.

    Returns:
        True when this caller claimed it. False when it was already claimed,
        whatever its status.
    """
    raise NotImplementedError


def finish_partition(
    connection: sqlite3.Connection,
    partition: str,
    now: str,
    rows_written: int | None = None,
    error: str | None = None,
) -> None:
    """
    Record how a partition ended.

    Call this AFTER the write, never before. Marking a partition done first
    means a crash produces one that is recorded as complete and is not, and no
    resume will ever go back for it. Redoing an idempotent partition costs time;
    skipping one costs data.

    Args:
        connection: an open connection.
        partition: the day.
        now: ISO timestamp for `finished_at`.
        rows_written: how many rows landed, on success.
        error: the failure, as a string, when there was one.

    Status becomes 'failed' when `error` is given and 'done' otherwise.
    """
    raise NotImplementedError


def partitions_to_run(connection: sqlite3.Connection, wanted: list[str]) -> list[str]:
    """
    What is left to do.

    Args:
        connection: an open connection.
        wanted: every partition the run covers, in order.

    Returns:
        The ones still needing work, in the order given. A partition is skipped
        only when its status is 'done'.

        A partition marked 'running' IS returned. It was interrupted, so it may
        have written some rows and may not have finished — which is exactly why
        the write has to be idempotent, and why the honest thing is to do it
        again rather than guess.

        A 'failed' partition is returned too. A failure is worth retrying; if it
        is going to fail again, it will.
    """
    raise NotImplementedError


def run_range(
    connection: sqlite3.Connection,
    partitions: list[str],
    work,
    now,
    max_consecutive_failures: int = 3,
) -> dict:
    """
    Run every outstanding partition, carrying on past failures.

    Stopping at the first failure is right for a daily run of one partition and
    wrong for a backfill of thirty: one bad day should not hide the fact that
    the other twenty-nine were fine.

    The exception is a failure meaning everything after it will also fail — the
    source is unreachable, the disk is full. Telling "this partition is bad"
    from "everything is bad" is genuinely hard, so the usual compromise is a
    consecutive-failure limit, on the reasonable guess that three in a row is no
    longer about the data.

    Args:
        connection: an open connection.
        partitions: every partition the run covers, in order.
        work: called as work(partition) and returns the number of rows written.
            Raising means that partition failed.
        now: called with no arguments, returns an ISO timestamp. Passed in so a
            test can control it.
        max_consecutive_failures: stop after this many in a row.

    Returns:
        A dict shaped:

            {
                "done": ["2026-03-05"],
                "failed": [{"partition": "2026-03-06", "error": "boom"}],
                "skipped": ["2026-03-04"],
                "stopped_early": False,
            }

        `skipped` holds partitions already done before this run started, which
        is what makes a resume visible rather than silent.
    """
    raise NotImplementedError
