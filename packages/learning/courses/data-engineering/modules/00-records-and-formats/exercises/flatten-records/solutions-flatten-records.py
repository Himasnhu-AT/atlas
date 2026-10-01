"""Shapes that nest: a worked solution."""

from __future__ import annotations


def flatten(document: dict, separator: str = ".") -> dict:
    out: dict = {}

    def walk(value: dict, prefix: str) -> None:
        for key, child in value.items():
            path = f"{prefix}{separator}{key}" if prefix else key
            if isinstance(child, dict):
                walk(child, path)
            else:
                out[path] = child

    walk(document, "")
    return out


def explode(document: dict, list_field: str) -> list[dict]:
    elements = document.get(list_field)
    if not isinstance(elements, list) or not elements:
        return []

    parent = {key: value for key, value in document.items() if key != list_field}
    flat_parent = flatten(parent)

    rows: list[dict] = []
    for element in elements:
        row = dict(flat_parent)
        if isinstance(element, dict):
            # The element wins a collision: it is the more specific claim.
            row.update(flatten(element))
        else:
            row[list_field] = element
        rows.append(row)
    return rows


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def double_counted(rows: list[dict], key_field: str, value_field: str) -> dict:
    counts: dict[str, int] = {}
    first_value: dict[str, float] = {}
    naive = 0.0

    for row in rows:
        key = row.get(key_field)
        value = _number(row.get(value_field))
        if key is None or value is None:
            continue

        key = str(key)
        counts[key] = counts.get(key, 0) + 1
        naive += value
        first_value.setdefault(key, value)

    repeated = sorted(key for key, count in counts.items() if count > 1)
    return {
        "keys": repeated,
        "naive_sum": naive,
        "true_sum": sum(first_value.values()),
    }


def schema_of(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        for key in row:
            counts[key] = counts.get(key, 0) + 1
    return counts
