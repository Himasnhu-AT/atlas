"""Reading a messy file: a worked solution."""

from __future__ import annotations


def split_fields(line: str, delimiter: str = ",") -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    in_quotes = False
    index = 0

    while index < len(line):
        char = line[index]

        if in_quotes:
            if char == '"':
                # Two in a row is one literal quote; one on its own closes.
                if index + 1 < len(line) and line[index + 1] == '"':
                    current.append('"')
                    index += 2
                    continue
                in_quotes = False
                index += 1
                continue
            current.append(char)
            index += 1
            continue

        # A quote only opens a quoted field at the start of one. A quote in the
        # middle of an unquoted field is literal text, which is what `csv` does
        # and is the difference between `say ""hi""` and `"say ""hi"""`.
        if char == '"' and not current:
            in_quotes = True
            index += 1
            continue

        if char == delimiter:
            fields.append("".join(current))
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    fields.append("".join(current))
    return fields


def parse_rows(text: str, delimiter: str = ",") -> list[dict]:
    lines = text.split("\n")
    # A trailing newline is a file ending politely, not an empty record.
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []

    header = split_fields(lines[0], delimiter)
    rows: list[dict] = []

    for line in lines[1:]:
        values = split_fields(line, delimiter)
        row: dict = {}
        for position, name in enumerate(header):
            row[name] = values[position] if position < len(values) else None
        rows.append(row)

    return rows


def check_shape(text: str, delimiter: str = ",") -> list[dict]:
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []

    expected = len(split_fields(lines[0], delimiter))
    problems: list[dict] = []

    for offset, line in enumerate(lines[1:], start=2):
        found = len(split_fields(line, delimiter))
        if found != expected:
            problems.append({"line": offset, "expected": expected, "found": found})

    return problems


def column_values(rows: list[dict], column: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        raw = row.get(column)
        if raw is None:
            continue
        stripped = raw.strip()
        if stripped == "":
            continue
        values.append(stripped)
    return values
