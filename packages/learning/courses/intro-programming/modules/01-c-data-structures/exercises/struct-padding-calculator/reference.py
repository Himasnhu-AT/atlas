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
    if not fields:
        return {
            "total_size": 0,
            "alignment": 1,
            "field_offsets": {},
            "padding_bytes": 0,
        }

    max_align = max(align for _, _, align in fields)
    current_offset = 0
    field_offsets: dict[str, int] = {}
    total_data_bytes = 0

    for name, size, align in fields:
        if align > 0 and (current_offset % align) != 0:
            current_offset = ((current_offset + align - 1) // align) * align
        field_offsets[name] = current_offset
        current_offset += size
        total_data_bytes += size

    if max_align > 0 and (current_offset % max_align) != 0:
        total_size = ((current_offset + max_align - 1) // max_align) * max_align
    else:
        total_size = current_offset

    padding_bytes = total_size - total_data_bytes

    return {
        "total_size": total_size,
        "alignment": max_align,
        "field_offsets": field_offsets,
        "padding_bytes": padding_bytes,
    }


def optimize_struct_layout(fields: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """
    Reorder fields to minimize internal padding.
    Orders fields by descending alignment, and secondary descending size.
    Preserves relative order among fields with identical alignment and size (stable sort).
    """
    return sorted(fields, key=lambda f: (f[2], f[1]), reverse=True)
