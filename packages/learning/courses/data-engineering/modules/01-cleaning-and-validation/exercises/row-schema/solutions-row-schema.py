"""A schema that reports: a worked solution."""

from __future__ import annotations


def validate_row(row: dict, rules: list[dict], row_number: int) -> dict:
    values: dict = {}
    errors: list[dict] = []

    for rule in rules:
        name = rule["name"]
        raw = row.get(name)
        absent = raw is None or (isinstance(raw, str) and raw.strip() == "")

        if absent:
            values[name] = None
            if rule.get("required"):
                errors.append({"field": name, "value": raw, "problem": "missing"})
            continue

        value, ok = rule["coerce"](raw)
        if ok:
            values[name] = value
        else:
            values[name] = None
            errors.append({"field": name, "value": raw, "problem": "invalid"})

    return {
        "row": row_number,
        "valid": not errors,
        "values": values,
        "errors": errors,
    }


def validate_extract(rows: list[dict], rules: list[dict], first_row_number: int = 2) -> dict:
    valid: list[dict] = []
    broken: list[dict] = []
    field_problems: dict[str, int] = {}

    for offset, row in enumerate(rows):
        result = validate_row(row, rules, first_row_number + offset)
        if result["valid"]:
            valid.append(result)
        else:
            broken.append(result)
            # Rows, not errors: the question is how many rows this field cost.
            for field in {error["field"] for error in result["errors"]}:
                field_problems[field] = field_problems.get(field, 0) + 1

    return {"valid": valid, "broken": broken, "field_problems": field_problems}


def is_usable(report: dict, max_broken_ratio: float = 0.01) -> bool:
    total = len(report["valid"]) + len(report["broken"])
    if total == 0:
        # An empty file is usually a failed export, not a quiet day.
        return False
    return len(report["broken"]) / total <= max_broken_ratio
