"""Freshness: a worked solution."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

SATURDAY = 5


def _parse(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    # Compare naive to naive. Mixing the two raises, and every timestamp in this
    # course is UTC.
    return parsed.replace(tzinfo=None)


def newest_row(connection: sqlite3.Connection, column: str = "placed_at") -> str | None:
    row = connection.execute(f"SELECT max({column}) FROM orders").fetchone()
    return row[0] if row and row[0] is not None else None


def age_in_hours(timestamp: str | None, now: str) -> float | None:
    if timestamp is None:
        return None
    # A bare date is midnight at the START of that day: the conservative
    # reading, which makes data look older rather than newer.
    return (_parse(now) - _parse(timestamp)).total_seconds() / 3600


def is_stale(timestamp: str | None, now: str, max_age_hours: float) -> bool:
    age = age_in_hours(timestamp, now)
    if age is None:
        # No data at all is not fresh.
        return True
    return age > max_age_hours


def business_hours_between(start: str, end: str) -> float:
    first = _parse(start)
    last = _parse(end)
    if last <= first:
        return 0.0

    total = 0.0
    cursor = first
    while cursor < last:
        # Step to the next hour boundary, or to the end, whichever is sooner.
        nxt = min(last, (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0))
        if nxt <= cursor:
            nxt = min(last, cursor + timedelta(hours=1))

        if cursor.weekday() < SATURDAY:
            total += (nxt - cursor).total_seconds() / 3600

        cursor = nxt

    return total


def freshness_verdict(
    last_run: str | None,
    newest: str | None,
    now: str,
    max_run_age_hours: float,
    max_data_age_hours: float,
) -> dict:
    run_age = age_in_hours(last_run, now)
    data_age = age_in_hours(newest, now)

    ran_recently = run_age is not None and run_age <= max_run_age_hours
    data_fresh = data_age is not None and data_age <= max_data_age_hours

    if ran_recently and data_fresh:
        state = "fresh"
    elif ran_recently:
        state = "source_stopped"
    elif data_fresh:
        state = "not_running"
    else:
        state = "stalled"

    return {
        "state": state,
        "ran_recently": ran_recently,
        "data_fresh": data_fresh,
        "run_age_hours": run_age,
        "data_age_hours": data_age,
    }
