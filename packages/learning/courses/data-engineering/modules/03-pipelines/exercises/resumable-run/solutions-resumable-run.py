"""The partial run: a worked solution."""

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
    connection.execute(CREATE_RUN_LOG)
    connection.commit()


def claim_partition(connection: sqlite3.Connection, partition: str, now: str) -> bool:
    cursor = connection.execute(
        "INSERT INTO run_log (partition, status, started_at) VALUES (?, 'running', ?) "
        "ON CONFLICT(partition) DO NOTHING",
        (partition, now),
    )
    connection.commit()
    # rowcount is 0 when the conflict was ignored, which means somebody else
    # already holds this partition.
    return cursor.rowcount == 1


def finish_partition(
    connection: sqlite3.Connection,
    partition: str,
    now: str,
    rows_written: int | None = None,
    error: str | None = None,
) -> None:
    connection.execute(
        "UPDATE run_log SET status = ?, rows_written = ?, error = ?, finished_at = ? "
        "WHERE partition = ?",
        ("failed" if error else "done", rows_written, error, now, partition),
    )
    connection.commit()


def partitions_to_run(connection: sqlite3.Connection, wanted: list[str]) -> list[str]:
    done = {
        row[0]
        for row in connection.execute("SELECT partition FROM run_log WHERE status = 'done'")
    }
    # Only 'done' is skipped. A 'running' partition was interrupted and may have
    # written some rows; doing it again is safe because the write is idempotent,
    # and guessing is not.
    return [partition for partition in wanted if partition not in done]


def run_range(
    connection: sqlite3.Connection,
    partitions: list[str],
    work,
    now,
    max_consecutive_failures: int = 3,
) -> dict:
    outstanding = partitions_to_run(connection, partitions)
    skipped = [p for p in partitions if p not in outstanding]

    done: list[str] = []
    failed: list[dict] = []
    consecutive = 0
    stopped_early = False

    for partition in outstanding:
        # An interrupted partition already holds a row, so a failed claim is not
        # a reason to skip it here: reset it and carry on.
        if not claim_partition(connection, partition, now()):
            connection.execute(
                "UPDATE run_log SET status = 'running', error = NULL, finished_at = NULL, "
                "started_at = ? WHERE partition = ?",
                (now(), partition),
            )
            connection.commit()

        try:
            written = work(partition)
        except Exception as error:  # noqa: BLE001 - a failure is a status here
            finish_partition(connection, partition, now(), error=str(error))
            failed.append({"partition": partition, "error": str(error)})
            consecutive += 1
            if consecutive >= max_consecutive_failures:
                stopped_early = True
                break
            continue

        finish_partition(connection, partition, now(), rows_written=written)
        done.append(partition)
        consecutive = 0

    return {
        "done": done,
        "failed": failed,
        "skipped": skipped,
        "stopped_early": stopped_early,
    }
