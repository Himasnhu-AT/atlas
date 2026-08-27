"""Loading a table: a worked solution."""

from __future__ import annotations

import sqlite3

CREATE_ORDERS = """
CREATE TABLE IF NOT EXISTS orders (
    order_id   INTEGER PRIMARY KEY,
    customer   TEXT NOT NULL,
    placed_at  TEXT NOT NULL,
    quantity   INTEGER,
    total      TEXT NOT NULL,
    status     TEXT NOT NULL
)
"""

COLUMNS = ["order_id", "customer", "placed_at", "quantity", "total", "status"]

# Table names cannot be parameterised, so the only ones this module will
# interpolate are the ones it knows about.
KNOWN_TABLES = {"orders", "customers"}


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_ORDERS)
    connection.commit()


def duplicate_keys(rows: list[dict], key: str = "order_id") -> dict:
    seen: dict = {}
    identical: set = set()
    conflicting: set = set()

    for row in rows:
        value = row.get(key)
        if value is None:
            continue

        if value not in seen:
            seen[value] = row
            continue

        if row == seen[value]:
            identical.add(value)
        else:
            conflicting.add(value)

    # A key that differs anywhere is conflicting, even if some of its copies
    # matched: "some of these agree" is not a reason to keep the first.
    identical -= conflicting

    return {
        "identical": sorted(identical),
        "conflicting": sorted(conflicting),
    }


def load_orders(connection: sqlite3.Connection, rows: list[dict]) -> dict:
    placeholders = ", ".join("?" for _ in COLUMNS)
    # `ON CONFLICT(order_id) DO NOTHING`, not `INSERT OR IGNORE`. OR IGNORE
    # ignores EVERY constraint violation, so a NULL in a NOT NULL column is
    # silently skipped and the row simply never arrives -- exactly the quiet
    # drop this course argues against. Naming the conflict target means only the
    # duplicate key is forgiven and everything else still raises.
    statement = (
        f"INSERT INTO orders ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT(order_id) DO NOTHING"
    )

    written = 0
    cursor = connection.cursor()
    try:
        for row in rows:
            values = [row.get(name) for name in COLUMNS]
            cursor.execute(statement, values)
            # rowcount is 0 when OR IGNORE swallowed a conflict.
            written += cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "received": len(rows),
        "written": written,
        "skipped": len(rows) - written,
    }


def row_count(connection: sqlite3.Connection, table: str = "orders") -> int:
    if table not in KNOWN_TABLES:
        raise ValueError(f"unknown table: {table}")
    cursor = connection.execute(f"SELECT count(*) FROM {table}")
    return int(cursor.fetchone()[0])
