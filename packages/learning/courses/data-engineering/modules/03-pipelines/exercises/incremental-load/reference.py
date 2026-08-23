"""Watermarks: a worked solution."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

CREATE_WATERMARKS = """
CREATE TABLE IF NOT EXISTS watermarks (
    name    TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

COLUMNS = ["order_id", "customer", "placed_at", "quantity", "total", "status"]


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_WATERMARKS)
    connection.commit()


def read_watermark(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM watermarks WHERE name = ?", (name,)
    ).fetchone()
    return row[0] if row else None


def rows_to_process(rows: list[dict], watermark: str | None, field: str = "placed_at") -> list[dict]:
    if watermark is None:
        return [row for row in rows if row.get(field) is not None]

    # `>=`, not `>`. Overlap is cheap and gaps are permanent.
    return [
        row
        for row in rows
        if row.get(field) is not None and row[field] >= watermark
    ]


def load_increment(
    connection: sqlite3.Connection,
    rows: list[dict],
    name: str = "orders",
    field: str = "placed_at",
) -> dict:
    current = read_watermark(connection, name)

    if not rows:
        # An empty run is not evidence that time has passed.
        return {"written": 0, "watermark": current}

    placeholders = ", ".join("?" for _ in COLUMNS)
    updates = ", ".join(f"{column} = excluded.{column}" for column in COLUMNS if column != "order_id")
    statement = (
        f"INSERT INTO orders ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(order_id) DO UPDATE SET {updates}"
    )

    highest = max(row[field] for row in rows)
    new_watermark = max(highest, current) if current else highest
    now = datetime.now(timezone.utc).isoformat()

    try:
        # One transaction covering both the rows and the mark that describes
        # them, so a crash costs a re-run rather than a silent hole.
        for row in rows:
            connection.execute(statement, [row.get(column) for column in COLUMNS])

        connection.execute(
            "INSERT INTO watermarks (name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (name, new_watermark, now),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {"written": len(rows), "watermark": new_watermark}
