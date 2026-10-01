"""Indexes and the plan: a worked solution."""

from __future__ import annotations

import re
import sqlite3

# Identifiers cannot be parameterised, so the ones that reach the query text are
# validated rather than trusted.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def explain(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> list[str]:
    rows = connection.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    # The description is the last column of each plan row.
    return [str(row[-1]) for row in rows]


def reads_every_row(plan: list[str]) -> bool:
    # A multi-table plan may search one and scan another. Any scan counts.
    return any("SCAN" in line.upper() for line in plan)


def _identifier(value: str) -> str:
    if not IDENTIFIER.match(value):
        raise ValueError(f"not a usable identifier: {value!r}")
    return value


def create_index(connection: sqlite3.Connection, name: str, table: str, columns: list[str]) -> None:
    safe_name = _identifier(name)
    safe_table = _identifier(table)
    if not columns:
        raise ValueError("an index needs at least one column")
    safe_columns = ", ".join(_identifier(column) for column in columns)

    connection.execute(
        f"CREATE INDEX IF NOT EXISTS {safe_name} ON {safe_table} ({safe_columns})"
    )
    connection.commit()


def same_rows(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
    rows = connection.execute(sql, params).fetchall()
    # Sorted, because row order is not part of a query's meaning unless the
    # query says ORDER BY, and it changes when the plan changes.
    return sorted(tuple(row) for row in rows)
