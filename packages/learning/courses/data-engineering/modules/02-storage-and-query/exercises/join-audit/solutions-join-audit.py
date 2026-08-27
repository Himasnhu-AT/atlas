"""The rows a join loses: a worked solution."""

from __future__ import annotations

import sqlite3


def joined_count(connection: sqlite3.Connection) -> dict:
    orders = connection.execute("SELECT count(*) FROM orders").fetchone()[0]
    joined = connection.execute(
        """
        SELECT count(*)
        FROM orders o
        JOIN customers c ON c.email = o.customer
        """
    ).fetchone()[0]

    return {"orders": orders, "joined": joined, "lost": orders - joined}


def unmatched_orders(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT o.order_id, o.customer
        FROM orders o
        LEFT JOIN customers c ON c.email = o.customer
        WHERE c.email IS NULL
        ORDER BY o.order_id
        """
    ).fetchall()

    # Normalised once, here, rather than inside the query, so the query itself
    # stays the naive one this exercise exists to measure.
    emails = {
        (row[0] or "").strip().lower()
        for row in connection.execute("SELECT email FROM customers")
    }

    out: list[dict] = []
    for order_id, customer in rows:
        raw = customer or ""
        normalised = raw.strip().lower()

        if normalised == "":
            reason = "missing"
        elif normalised in emails:
            reason = "normalising"
        else:
            reason = "unknown"

        out.append({"order_id": order_id, "customer": raw, "reason": reason})

    return out


def multiplying_keys(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT email
        FROM customers
        GROUP BY email
        HAVING count(*) > 1
        ORDER BY email
        """
    ).fetchall()
    return [row[0] for row in rows]


def join_is_safe(connection: sqlite3.Connection) -> dict:
    counts = joined_count(connection)
    multiplied = multiplying_keys(connection)
    return {
        "lost": counts["lost"],
        "multiplied": multiplied,
        "safe": counts["lost"] == 0 and not multiplied,
    }
