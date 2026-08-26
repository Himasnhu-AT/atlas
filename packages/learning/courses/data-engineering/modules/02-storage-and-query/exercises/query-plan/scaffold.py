"""
Indexes and the plan.

The database will tell you exactly what it is about to do, in one line. Reading
that line is the cheapest performance skill there is.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3


def explain(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> list[str]:
    """
    The query plan, as lines of text.

    `EXPLAIN QUERY PLAN <sql>` returns rows whose last column is the human
    readable description. Collect those, in order.

    Args:
        connection: an open connection.
        sql: the SELECT to explain. Not executed, only planned.
        params: the parameters the query would take. The planner needs them
            present, though their values do not affect the plan here.

    Returns:
        One string per plan row, for example:

            ["SCAN orders"]
            ["SEARCH orders USING INDEX orders_customer (customer=?)"]
    """
    raise NotImplementedError


def reads_every_row(plan: list[str]) -> bool:
    """
    Whether this plan reads the whole table.

    Args:
        plan: the output of `explain`.

    Returns:
        True when any line describes a scan of a table.

        This is the entire skill: SCAN is reading everything and SEARCH is not,
        and one word tells you which. On ten rows a scan is free; on ten million
        it is the whole problem, and the query text looks identical either way.

        Note that `SCAN` can appear as part of a longer line, and that a plan
        with several rows may scan one table while searching another. Any scan
        means at least one query input is read end to end.
    """
    raise NotImplementedError


def create_index(connection: sqlite3.Connection, name: str, table: str, columns: list[str]) -> None:
    """
    Create an index, if it does not already exist.

    Args:
        connection: an open connection.
        name: the index name.
        table: the table to index.
        columns: the columns, IN ORDER. The order matters: an index on
            (customer, placed_at) helps a query filtering on customer, and one
            filtering on both, and does NOT help one filtering only on
            placed_at. Same reason a phone book sorted by surname then first
            name cannot find every Aditi.

    None of these three can be parameterised, because SQL does not allow a
    parameter where an identifier goes. Validate them instead: accept only
    names made of letters, digits and underscores, and raise ValueError
    otherwise. This is the same reasoning as `row_count` in the last exercise.
    """
    raise NotImplementedError


def same_rows(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
    """
    Run a query and return its rows, sorted so two runs can be compared.

    An index is meant to change the speed and nothing else. A query returning
    different rows with an index than without it means something is wrong with
    the query, not the index — and without sorting, a comparison would also trip
    over row order, which a database is free to change at any time and does when
    the plan changes.

    Args:
        connection: an open connection.
        sql: the query.
        params: its parameters.

    Returns:
        The rows as tuples, sorted.
    """
    raise NotImplementedError
