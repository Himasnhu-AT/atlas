"""
Coercion and what it costs.

Four coercions. Each takes a string and returns a value AND whether it worked,
because a function that can fail and returns only a value has to encode failure
as a value, and every value it could pick is also a legitimate answer.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from decimal import Decimal


def to_int(raw: str | None) -> tuple[int | None, bool]:
    """
    Read an integer.

    Args:
        raw: the field as it arrived. May be None (absent) or "" (present and
            empty). Both fail, and they fail the same way here; keeping them
            apart is the row validator's job, not this one's.

    Returns:
        (value, ok). On success, (the integer, True). On failure, (None, False).

        Surrounding whitespace is ignored. A leading "+" or "-" is fine. A value
        with a decimal point fails rather than truncating: "2.7" items is not
        two items, it is a field that does not mean what you assumed.

    Examples:
        >>> to_int(" 42 ")
        (42, True)
        >>> to_int("unknown")
        (None, False)
        >>> to_int("2.7")
        (None, False)
    """
    raise NotImplementedError


def to_decimal(raw: str | None) -> tuple[Decimal | None, bool]:
    """
    Read a money amount.

    Decimal, not float. A float cannot hold 0.10 exactly, so a column of them
    drifts, and the drift shows up as a total that is out by a cent in a report
    somebody has to explain.

    Args:
        raw: the field as it arrived. Totals in this extract turn up as plain
            numbers, with a currency symbol glued on, and with a thousands
            comma inside quotes.

    Returns:
        (value, ok). Strip a leading currency symbol from "$€£" and any commas
        used as thousands separators, then parse.

        Do NOT strip a comma used as a decimal separator, because you cannot
        tell which it is from one value. This function treats every comma as a
        thousands separator, which is the right call for this source and the
        wrong call for a European one. Assumptions like that belong in a
        docstring where the next person will find them.

    Examples:
        >>> to_decimal("$59.00")
        (Decimal('59.00'), True)
        >>> to_decimal("1,499.00")
        (Decimal('1499.00'), True)
        >>> to_decimal("free")
        (None, False)
    """
    raise NotImplementedError


def to_date(raw: str | None, day_first: bool = True) -> tuple[str | None, bool]:
    """
    Read a date, normalising to ISO.

    Three spellings appear in this extract: "2026-03-01", "01/03/2026", and
    "2026-03-02T09:14:00".

    Args:
        raw: the field as it arrived.
        day_first: how to read the ambiguous slash format. "01/03/2026" is the
            first of March in most of the world and the third of January in the
            United States, and nothing in the file says which. The caller has to
            decide, which is why this is a parameter and not a guess.

    Returns:
        (value, ok) where value is "YYYY-MM-DD". A timestamp keeps only its date
        part: the question this column answers is which day the order was
        placed, and carrying a time that some rows have and others do not means
        every later comparison has to handle both.

        A date that does not exist, like "31/02/2026", fails rather than rolling
        into March.

    Examples:
        >>> to_date("2026-03-01")
        ('2026-03-01', True)
        >>> to_date("01/03/2026")
        ('2026-03-01', True)
        >>> to_date("01/03/2026", day_first=False)
        ('2026-01-03', True)
    """
    raise NotImplementedError


def to_bool(raw: str | None) -> tuple[bool | None, bool]:
    """
    Read a boolean.

    Args:
        raw: the field as it arrived. Sources spell this a dozen ways.

    Returns:
        (value, ok). These map to True: "true", "t", "yes", "y", "1".
        These map to False: "false", "f", "no", "n", "0".
        Case and surrounding whitespace do not matter. Anything else fails.

        Note what is not on either list: "" and None. An empty boolean is not
        False. It is a question nobody answered, and a pipeline that reads it as
        False is inventing a "no" that the source never sent.
    """
    raise NotImplementedError
