from __future__ import annotations

from typing import Any


def calculate_struct_layout(fields: list[tuple[str, int, int]]) -> dict[str, Any]:
    """
    Calculate the byte offsets, total size, alignment requirement, and padding bytes
    for a struct composed of the given fields in declaration order.

    Each field is represented as a tuple: (name, size, alignment).
    All fields are placed at an offset that is a multiple of their individual alignment.
    The total size of the struct is rounded up to a multiple of the struct's maximum alignment
    (or 1 if fields is empty).

    Returns a dict with:
        "total_size": int
        "alignment": int (maximum alignment among fields, or 1 if empty)
        "field_offsets": dict[str, int] (mapping field name to byte offset)
        "padding_bytes": int (total bytes of internal and trailing padding)
    """
    raise NotImplementedError


def optimize_struct_layout(fields: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """
    Reorder fields to minimize internal padding.
    Orders fields by descending alignment, and secondary descending size.
    Preserves relative order among fields with identical alignment and size (stable sort).
    """
    raise NotImplementedError
