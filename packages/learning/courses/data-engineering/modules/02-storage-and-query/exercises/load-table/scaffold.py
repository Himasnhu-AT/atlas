"""
Loading a table.

Create the table, load in one transaction, and decide what a duplicate means.
Every one of those is a decision the load makes on your behalf if you do not
make it yourself.

`sqlite3` is in the standard library. The tests hand you an in-memory connection,
so nothing here touches disk.

Run `python3 test.py` when you want to see how you are doing.
"""

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


def create_schema(connection: sqlite3.Connection) -> None:
    """
    Create the orders table.

    `CREATE_ORDERS` above is the schema, and it is worth reading rather than
    running past:

      - `quantity` is the only nullable column, because an order can ship
        without us knowing how many items, and it cannot exist without a
        customer.
      - `total` is TEXT holding the exact decimal. sqlite has no decimal type
        and REAL is a float, and a column of floats holding money drifts until
        a report is out by a cent nobody can explain.
      - `placed_at` is TEXT holding ISO 8601, which sqlite compares correctly as
        strings because ISO dates sort lexicographically. That is the whole
        reason the format was worth normalising to.

    Args:
        connection: an open sqlite3 connection.
    """
    raise NotImplementedError


def duplicate_keys(rows: list[dict], key: str = "order_id") -> dict:
    """
    Find keys that appear more than once, and whether the rows agree.

    Run this BEFORE choosing how to handle conflicts. "Keep the first" is only
    honest when the duplicates are identical; when they differ it keeps whichever
    arrived first, which has nothing to do with which is correct.

    Args:
        rows: cleaned rows, each a dict of column name to value.
        key: the column that should be unique.

    Returns:
        A dict shaped:

            {"identical": [1003], "conflicting": [1009]}

        `identical` holds keys whose duplicate rows are equal in every column.
        `conflicting` holds keys whose rows differ somewhere. Both are sorted.

        A key is conflicting if any copy differs from the first copy, even when
        other copies agree. Rows missing the key are ignored by this report.

        A key that appears once is in neither list.
    """
    raise NotImplementedError


def load_orders(connection: sqlite3.Connection, rows: list[dict]) -> dict:
    """
    Load rows into the orders table, in one transaction.

    One transaction, not one per row. A separate transaction per row means an
    fsync per row, so a load that should take a second takes minutes. The more
    important reason is atomicity: a load that dies halfway with no transaction
    leaves the table holding part of an extract, and nothing in the table says
    which part.

    Use parameters, never string formatting. In a pipeline the attacker is
    usually not a person, it is a customer name containing an apostrophe, and
    the result is a crash at three in the morning.

    Duplicates are skipped rather than replacing what is there, which is the
    right call for this extract because its duplicate rows are identical. That
    is a decision, and `duplicate_keys` is how you check it still holds.

    Skip the duplicate by NAMING the conflict:

        INSERT INTO orders (...) VALUES (...) ON CONFLICT(order_id) DO NOTHING

    and not with `INSERT OR IGNORE`. OR IGNORE is the obvious spelling and it is
    too broad: it ignores every constraint violation, so a NULL in a NOT NULL
    column is silently skipped too and the row just never arrives. That is the
    quiet drop this whole course is about, arriving through the one line you
    wrote to be careful.

    `cursor.rowcount` is 0 when a conflict was ignored and 1 when a row was
    written, which is where the counts below come from.

    Args:
        connection: an open connection with the schema already created.
        rows: cleaned rows. Keys are column names.

    Returns:
        A dict shaped:

            {"received": 10, "written": 9, "skipped": 1}

        A load that says "done" tells you nothing. A load that says
        "10 in, 9 written, 1 skipped" is one you can leave running unattended.
    """
    raise NotImplementedError


def row_count(connection: sqlite3.Connection, table: str = "orders") -> int:
    """
    How many rows the table holds.

    Args:
        connection: an open connection.
        table: the table name. This one is interpolated rather than parameterised
            because SQL does not allow a parameter where a table name goes. That
            makes it the one place in this file where a caller-supplied string
            reaches the query text, so it is validated against a fixed list
            rather than trusted.

    Returns:
        The count. Raises ValueError for a table this function does not know
        about, rather than passing the name through to the database.
    """
    raise NotImplementedError
