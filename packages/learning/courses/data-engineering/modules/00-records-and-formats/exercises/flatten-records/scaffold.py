"""
Shapes that nest.

Turning a document into rows is a design decision, and the wrong one is not
detectable later. These four functions are the decision, written down.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def flatten(document: dict, separator: str = ".") -> dict:
    """
    Flatten nested dicts into one level, joining keys with a separator.

    Args:
        document: a decoded JSON object. Values may be dicts, lists, or scalars.
        separator: what joins a parent key to a child key.

    Returns:
        A flat dict. A nested dict becomes several keys:

            {"customer": {"email": "a@b.c"}} -> {"customer.email": "a@b.c"}

        A list is left alone, as a list, under its own key. Flattening a list
        into `items.0.sku`, `items.1.sku` is possible and is almost always
        wrong: the column names then depend on how many items an order happened
        to have, so two orders produce two different schemas. `explode` below is
        the honest way to handle a list.

        An empty dict as a value disappears, because it contributes no leaves.
        That is worth knowing rather than discovering: a document whose customer
        object is `{}` flattens to a row with no customer keys at all.

    Examples:
        >>> flatten({"a": 1, "b": {"c": 2}})
        {'a': 1, 'b.c': 2}
    """
    raise NotImplementedError


def explode(document: dict, list_field: str) -> list[dict]:
    """
    One row per element of a list field, each carrying the parent's other fields.

    Args:
        document: a decoded JSON object.
        list_field: the key holding a list.

    Returns:
        One dict per element. Each is the parent's fields minus `list_field`,
        with the element's fields merged in and flattened.

        A key collision resolves in favour of the element, since the element is
        the more specific claim.

        An empty list gives [], not one row of parent fields. An order with no
        items produced no item rows, and inventing one would put a row in the
        table for something that does not exist.

        A missing `list_field` also gives [], for the same reason.

    Examples:
        >>> explode({"id": 1, "items": [{"sku": "A"}, {"sku": "B"}]}, "items")
        [{'id': 1, 'sku': 'A'}, {'id': 1, 'sku': 'B'}]
    """
    raise NotImplementedError


def double_counted(rows: list[dict], key_field: str, value_field: str) -> dict:
    """
    Find values that would be counted more than once by a naive sum.

    This is the check that catches the classic explode bug. After exploding an
    order into one row per item, the order's total appears on every one of those
    rows, so summing it gives a number that is too big and looks plausible.

    Args:
        rows: exploded rows.
        key_field: the parent's identity, for example "order_id".
        value_field: a parent-level value that got copied onto each row.

    Returns:
        A dict shaped:

            {"keys": ["1003"], "naive_sum": 2998.0, "true_sum": 1499.0}

        `keys` holds every key that appears on more than one row, sorted, as
        strings. `naive_sum` is what summing the column gives. `true_sum` counts
        each key's value once.

        Rows whose value is missing or not a number are skipped for both sums
        rather than treated as zero. A value nobody can read is not evidence
        that the value was nothing.

        Returns zeroes and an empty key list for empty input.
    """
    raise NotImplementedError


def schema_of(rows: list[dict]) -> dict:
    """
    What fields these rows have, and how consistently.

    Args:
        rows: any list of flat dicts.

    Returns:
        A dict mapping field name to the number of rows that have it, present
        or not. Sorted is not required; equality on dicts ignores order.

        This is the cheapest useful thing you can say about an unfamiliar
        extract, and it is how you notice that a field you assumed was always
        there is present on 9,998 rows out of 10,000.

        Empty rows give an empty dict.
    """
    raise NotImplementedError
