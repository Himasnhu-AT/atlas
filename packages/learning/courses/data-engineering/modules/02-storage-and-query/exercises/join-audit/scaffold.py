"""
The rows a join loses.

An inner join drops rows that do not match, silently, and the result is a
perfectly good table with a wrong number in it. Four small queries that turn
that into a number somebody can look at.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import sqlite3


def joined_count(connection: sqlite3.Connection) -> dict:
    """
    How many orders there are, and how many survive the join to customers.

    The join is on `customers.email = orders.customer`, on the raw values. Do
    not normalise here: the whole point of the exercise is to see what the naive
    join costs before deciding where to fix it.

    Args:
        connection: an open connection holding `orders` and `customers`.

    Returns:
        A dict shaped:

            {"orders": 9, "joined": 7, "lost": 2}

        `lost` is what nobody notices. It should be recorded by the pipeline
        next to the row counts it already keeps, and compared to yesterday's: a
        join that has always dropped two rows is a known issue, and one that
        dropped two yesterday and four hundred today is an incident.
    """
    raise NotImplementedError


def unmatched_orders(connection: sqlite3.Connection) -> list[dict]:
    """
    The orders the join threw away, with a guess at why.

    Args:
        connection: an open connection.

    Returns:
        One dict per unmatched order, sorted by order_id:

            {"order_id": 1008, "customer": "", "reason": "missing"}

        `reason` is one of:

          - "missing"     the order has no customer value at all, or an empty one
          - "normalising" trimming and lowercasing the value WOULD match a
                          customer, so the two systems agree and the strings do
                          not
          - "unknown"     the customer is a real value that matches nothing

        Those three want different fixes and it matters which is which.
        "missing" is a data problem and the row belongs in a quarantine.
        "normalising" belongs at the coercion layer, not patched into every
        query with lower(trim(...)) — which also throws away the index.
        "unknown" is either a genuinely new customer or a stale reference table,
        which is the next module's subject.
    """
    raise NotImplementedError


def multiplying_keys(connection: sqlite3.Connection) -> list[str]:
    """
    Reference rows that would multiply the join.

    If `customers` holds two rows for the same email, every one of that
    customer's orders comes out of the join twice, along with its total. This is
    the same double counting as exploding a nested list, arriving by a different
    route.

    Args:
        connection: an open connection.

    Returns:
        Every email appearing more than once in `customers`, sorted. Empty when
        the table is unique on email, which is what you hope and not what you
        assume.
    """
    raise NotImplementedError


def join_is_safe(connection: sqlite3.Connection) -> dict:
    """
    The check to run after a join, every time.

    Args:
        connection: an open connection.

    Returns:
        A dict shaped:

            {"lost": 2, "multiplied": [], "safe": False}

        `safe` is True only when the join lost nothing and multiplied nothing:
        the output of a join to a reference table should have exactly as many
        rows as the input.

        Note what `safe` does NOT mean. It does not mean the data is right. It
        means the join did not change the row count, which is the one thing a
        join is not supposed to do and the one thing nothing else will tell you.
    """
    raise NotImplementedError
