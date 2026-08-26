"""
Watermarks.

An incremental load needs to know where it got to. The obvious answer loses rows
quietly, which is the worst way for something to be wrong.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3

CREATE_WATERMARKS = """
CREATE TABLE IF NOT EXISTS watermarks (
    name    TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def create_schema(connection: sqlite3.Connection) -> None:
    """
    Create the watermarks table.

    A watermark is named, because a pipeline has more than one source and each
    gets to a different place.
    """
    raise NotImplementedError


def read_watermark(connection: sqlite3.Connection, name: str) -> str | None:
    """
    Where the last run got to.

    Args:
        connection: an open connection.
        name: which watermark.

    Returns:
        The stored value, or None if this source has never been loaded. None
        means "load everything", which is the correct behaviour for a first run
        and is worth being explicit about rather than defaulting to an
        arbitrary date.
    """
    raise NotImplementedError


def rows_to_process(rows: list[dict], watermark: str | None, field: str = "placed_at") -> list[dict]:
    """
    Select the rows a run should handle.

    Use `>=`, not `>`.

    Two rows can share a timestamp. With a strict `>`, if the last run ended on
    a row at 09:14:00 and another row exists at exactly 09:14:00, that row is
    skipped and no later run will ever pick it up, because the mark has already
    moved past it. Nothing raises.

    `>=` re-reads the boundary rows every run, which is fine: the write is an
    upsert, so re-writing an unchanged row costs almost nothing. Overlap is
    cheap and gaps are permanent.

    Args:
        rows: everything available from the source.
        watermark: where the last run got to, or None for a first run.
        field: the timestamp column to compare on. ISO 8601 strings compare
            correctly as strings, which is the whole reason the previous module
            normalised to that format.
            This course's fixture stores dates without offsets. If an input may
            mix UTC-offset spellings, normalise them before calling this
            function rather than comparing different timestamp designs as text.

    Returns:
        The rows at or after the watermark, in their original order. All of them
        when the watermark is None. Rows missing the field are skipped rather
        than crashing the run: they cannot be placed in time, and the validator
        should already have caught them.
    """
    raise NotImplementedError


def load_increment(
    connection: sqlite3.Connection,
    rows: list[dict],
    name: str = "orders",
    field: str = "placed_at",
) -> dict:
    """
    Write the rows and move the watermark, atomically.

    Both in ONE transaction. If the watermark is committed separately, a crash
    between the two leaves a mark claiming you loaded rows you did not, and no
    later run will go back for them.

    Upsert on `order_id` so a re-run corrects rather than duplicates. The rows
    at the boundary arrive again on every run by design, and this is what makes
    that harmless.

    Args:
        connection: an open connection holding `orders` and `watermarks`.
        rows: the rows this run should write. Already selected by
            `rows_to_process`.
        name: the watermark to move.
        field: the timestamp column the watermark tracks.

    Returns:
        A dict shaped:

            {"written": 4, "watermark": "2026-03-07"}

        `written` counts rows sent to the database, including ones that
        overwrote an identical row: they were processed, and reporting them as
        skipped would make a normal re-run look like it did nothing.

        The new watermark is the highest value of `field` among the rows
        written, never earlier than the existing mark. When there are no rows,
        the watermark does not move and the old value is returned: an empty run
        is not evidence that time has passed.

        On any write failure, roll back both the rows and the watermark.
    """
    raise NotImplementedError
