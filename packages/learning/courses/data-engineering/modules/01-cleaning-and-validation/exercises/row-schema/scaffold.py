"""
A schema that reports.

Validation that raises tells you about one row. Validation that collects tells
you about the extract, which is the thing somebody is about to ask you about.

You may import your coercions from the previous exercise's ideas, but everything
you need is passed in: a rule carries its own coercion function.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def validate_row(row: dict, rules: list[dict], row_number: int) -> dict:
    """
    Apply every rule to one row and collect what went wrong.

    Args:
        row: one parsed record. A value may be a string, "" (present and empty),
            or None (absent entirely).
        rules: each shaped:

                {"name": "quantity", "coerce": to_int, "required": True}

            `coerce` takes the raw value and returns (value, ok), exactly like
            the previous exercise's functions.
        row_number: the number this row has in the SOURCE, not its position in
            some filtered list. Renumbering makes every error point at the wrong
            line, and nobody notices until they open the file.

    Returns:
        A dict shaped:

            {
                "row": 6,
                "valid": False,
                "values": {"order_id": 1006, "quantity": None},
                "errors": [
                    {"field": "quantity", "value": "unknown",
                     "problem": "not an integer"},
                ],
            }

        `values` holds every field that coerced successfully. A field that
        failed is present with value None, so the shape is the same for every
        row and a caller does not have to check whether a key exists.

        An error's `problem` is "missing" when a required field is absent or
        empty, and "invalid" when a value was present and would not coerce.
        Those are different failures with different owners: one says the source
        is not sending you something, the other says it is sending you nonsense.

        An optional field that is absent or empty is not an error. It coerces to
        None and the row stays valid.

        `valid` is True when `errors` is empty.
    """
    raise NotImplementedError


def validate_extract(rows: list[dict], rules: list[dict], first_row_number: int = 2) -> dict:
    """
    Run the validator over a whole extract.

    Args:
        rows: parsed records, in file order.
        rules: as above.
        first_row_number: the source line number of `rows[0]`. Defaults to 2,
            because line 1 of a CSV is the header.

    Returns:
        A dict shaped:

            {
                "valid": [ ...validate_row results that passed... ],
                "broken": [ ...the ones that did not... ],
                "field_problems": {"quantity": 2, "status": 1},
            }

        Both lists hold the full result dicts, not the input rows: the caller
        needs the coerced values from the good ones and the errors from the bad.

        `field_problems` counts how many rows had at least one error in each
        field. Rows, not errors, so one row failing twice on the same field
        counts once — the question it answers is "how many rows did this field
        cost me".

        This summary is what somebody looks at first. One row failing is noise.
        Four hundred rows failing the same field is a change upstream.
    """
    raise NotImplementedError


def is_usable(report: dict, max_broken_ratio: float = 0.01) -> bool:
    """
    Whether an extract is worth loading at all.

    Args:
        report: the output of validate_extract.
        max_broken_ratio: the share of rows allowed to be broken.

    Returns:
        True when the broken share is at or below the threshold.

        An extract with no rows at all returns False. That is a decision worth
        seeing: an empty file is usually a failed export rather than a quiet day,
        and treating it as "nothing to do" is how a pipeline reports success
        having loaded nothing.
    """
    raise NotImplementedError
