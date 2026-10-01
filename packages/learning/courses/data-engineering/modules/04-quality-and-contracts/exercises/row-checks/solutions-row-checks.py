"""Counting is a test: a worked solution."""

from __future__ import annotations

import sqlite3
import statistics
from decimal import Decimal, InvalidOperation

# How many offending values are worth printing before a count is more useful.
MAX_LISTED = 5


def _columns_of(connection: sqlite3.Connection, table: str = "orders") -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _within(value: float, history: list[float], tolerance: float) -> tuple[bool, float]:
    baseline = statistics.median(history)
    if baseline == 0:
        return value == 0, 0.0
    drift = abs(value - baseline) / baseline
    return drift <= tolerance, drift


def check_row_count(connection: sqlite3.Connection, history: list[int], tolerance: float = 0.5) -> dict:
    count = connection.execute("SELECT count(*) FROM orders").fetchone()[0]

    if not history:
        return {
            "name": "row_count",
            "passed": True,
            "detail": f"{count} rows, no history to compare against",
        }

    passed, drift = _within(count, [float(n) for n in history], tolerance)
    baseline = statistics.median(history)
    return {
        "name": "row_count",
        "passed": passed,
        "detail": f"{count} rows against a median of {baseline:g}, {drift:.0%} away",
    }


def check_no_nulls(connection: sqlite3.Connection, columns: list[str]) -> dict:
    known = _columns_of(connection)
    unknown = [column for column in columns if column not in known]
    if unknown:
        raise ValueError(f"not columns of orders: {unknown}")

    found: dict[str, int] = {}
    for column in columns:
        count = connection.execute(
            f"SELECT count(*) FROM orders WHERE {column} IS NULL"
        ).fetchone()[0]
        if count:
            found[column] = count

    detail = (
        "no nulls"
        if not found
        else ", ".join(f"{column}: {count}" for column, count in sorted(found.items()))
    )
    return {"name": "no_nulls", "passed": not found, "detail": detail}


def check_unique(connection: sqlite3.Connection, column: str = "order_id") -> dict:
    if column not in _columns_of(connection):
        raise ValueError(f"not a column of orders: {column}")

    rows = connection.execute(
        f"SELECT {column} FROM orders GROUP BY {column} HAVING count(*) > 1 ORDER BY {column}"
    ).fetchall()
    values = [row[0] for row in rows]

    if not values:
        detail = f"{column} is unique"
    elif len(values) <= MAX_LISTED:
        detail = f"repeated: {', '.join(str(value) for value in values)}"
    else:
        detail = f"{len(values)} repeated values"

    return {"name": "unique", "passed": not values, "detail": detail}


def check_allowed_values(connection: sqlite3.Connection, column: str, allowed: set) -> dict:
    if column not in _columns_of(connection):
        raise ValueError(f"not a column of orders: {column}")

    rows = connection.execute(
        f"SELECT DISTINCT {column} FROM orders WHERE {column} IS NOT NULL"
    ).fetchall()
    unexpected = sorted(str(row[0]) for row in rows if row[0] not in allowed)

    detail = (
        "all values known"
        if not unexpected
        else f"unexpected: {', '.join(unexpected[:MAX_LISTED])}"
    )
    return {"name": "allowed_values", "passed": not unexpected, "detail": detail}


def check_sum_in_range(
    connection: sqlite3.Connection,
    column: str,
    history: list[float],
    tolerance: float = 0.5,
) -> dict:
    if column not in _columns_of(connection):
        raise ValueError(f"not a column of orders: {column}")

    total = Decimal("0")
    unreadable = 0
    for (raw,) in connection.execute(f"SELECT {column} FROM orders"):
        if raw is None:
            continue
        try:
            total += Decimal(str(raw))
        except InvalidOperation:
            unreadable += 1

    note = f", {unreadable} unreadable" if unreadable else ""

    if not history:
        return {
            "name": "sum_in_range",
            "passed": True,
            "detail": f"{total} total, no history to compare against{note}",
        }

    passed, drift = _within(float(total), history, tolerance)
    baseline = statistics.median(history)
    return {
        "name": "sum_in_range",
        "passed": passed,
        "detail": f"total {total} against a median of {baseline:g}, {drift:.0%} away{note}",
    }


def run_checks(checks: list[dict]) -> dict:
    failed = [check["name"] for check in checks if not check["passed"]]
    return {"passed": not failed, "failed": failed, "results": list(checks)}
