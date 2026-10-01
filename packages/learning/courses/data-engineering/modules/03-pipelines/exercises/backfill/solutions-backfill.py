"""Backfills: a worked solution."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

COLUMNS = ["order_id", "customer", "placed_at", "quantity", "total", "status"]


def days_between(start: str, end: str) -> list[str]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if first > last:
        # A backfill over an empty range is a no-op, not an error.
        return []

    out: list[str] = []
    cursor = first
    while cursor <= last:
        out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def run_partition(connection: sqlite3.Connection, day: str, rows: list[dict]) -> dict:
    # A run owns one partition. Rows for another day are not this run's to write.
    mine = [row for row in rows if row.get("placed_at") == day]

    placeholders = ", ".join("?" for _ in COLUMNS)
    insert = f"INSERT INTO orders ({', '.join(COLUMNS)}) VALUES ({placeholders})"

    try:
        cursor = connection.execute("DELETE FROM orders WHERE placed_at = ?", (day,))
        deleted = cursor.rowcount

        for row in mine:
            connection.execute(insert, [row.get(column) for column in COLUMNS])

        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {"day": day, "deleted": max(deleted, 0), "written": len(mine)}


def backfill(connection: sqlite3.Connection, start: str, end: str, source: dict) -> dict:
    per_day: list[dict] = []
    written = 0
    deleted = 0

    for day in days_between(start, end):
        result = run_partition(connection, day, source.get(day, []))
        per_day.append(result)
        written += result["written"]
        deleted += result["deleted"]

    return {
        "days": len(per_day),
        "written": written,
        "deleted": deleted,
        "per_day": per_day,
    }
