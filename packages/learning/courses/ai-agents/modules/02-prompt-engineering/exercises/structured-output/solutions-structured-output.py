"""
Structured output: worked solution.

Recover an object from a messy reply, validate it, and retry with the validator's
own message handed back to the model.
"""

from __future__ import annotations

import json


class ExtractionError(Exception):
    """No usable JSON object could be recovered from the reply."""


class ValidationError(Exception):
    """The parsed object did not match the schema."""


#: Schema type name to the Python types that satisfy it. bool is deliberately
#: absent from "integer" and "number": it is a subclass of int, so leaving it in
#: would let `true` pass as a quantity.
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def find_json_object(text: str) -> str:
    """The first brace balanced object, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        raise ExtractionError("no JSON object in the reply: there is no opening brace")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        character = text[index]

        if in_string:
            # An escape consumes exactly the next character, which is how
            # \" stays inside the string and \\" ends it.
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ExtractionError(
        "the JSON object never closes, which usually means the reply was cut off"
    )


def _strip_fence(text: str) -> str | None:
    """The body of a markdown code fence, or None when there is not one."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return None
    # Drop the opening line, which may carry a language tag, and the closing
    # fence if it is there. A missing closing fence is a truncated reply, and
    # the caller's next strategy still gets a chance at it.
    body = stripped.split("\n", 1)[1] if "\n" in stripped else ""
    end = body.rfind("```")
    return body[:end] if end != -1 else body


def extract_json(text: str) -> dict:
    """Cheapest strategy first: clean, then fenced, then scanned."""
    candidates = [text.strip()]

    fenced = _strip_fence(text)
    if fenced is not None:
        candidates.append(fenced.strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
        raise ExtractionError(
            f"expected a JSON object with named fields, got {type(parsed).__name__}"
        )

    # find_json_object raises ExtractionError itself when there is nothing to
    # find, so the failure message stays specific either way.
    snippet = find_json_object(text)
    try:
        parsed = json.loads(snippet)
    except ValueError as error:
        raise ExtractionError(f"found an object but could not parse it: {error}") from error

    if not isinstance(parsed, dict):
        raise ExtractionError(
            f"expected a JSON object with named fields, got {type(parsed).__name__}"
        )
    return parsed


def validate(data: dict, schema: dict) -> None:
    """Check the fields you consume, in the schema's order."""
    for field, spec in schema.items():
        required = spec.get("required", True)
        nullable = spec.get("nullable", False)

        if field not in data:
            if required:
                raise ValidationError(f"{field}: required field is missing")
            continue

        value = data[field]

        if value is None:
            if nullable:
                continue
            raise ValidationError(f"{field}: is null, and null is not allowed here")

        expected = spec.get("type")
        if expected is not None:
            allowed = _TYPES.get(expected)
            if allowed is None:
                raise ValidationError(f"{field}: schema names an unknown type {expected!r}")
            # bool first, because isinstance(True, int) is True and every
            # numeric check below would otherwise accept it.
            if isinstance(value, bool) and expected != "boolean":
                raise ValidationError(f"{field}: expected {expected}, got bool")
            if not isinstance(value, allowed):
                raise ValidationError(
                    f"{field}: expected {expected}, got {type(value).__name__}"
                )

        if "enum" in spec and value not in spec["enum"]:
            allowed_values = ", ".join(repr(option) for option in spec["enum"])
            raise ValidationError(f"{field}: {value!r} is not one of {allowed_values}")


def extract_with_retry(
    client,
    prompt: str,
    schema: dict,
    *,
    max_attempts: int = 3,
) -> dict:
    """One call, then up to max_attempts - 1 corrections with the error attached."""
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

    messages: list[dict] = [{"role": "user", "content": prompt}]
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        response = client.chat.completions.create(model="mock", messages=messages)
        choice = response.choices[0]
        raw = choice.message.content or ""

        try:
            if choice.finish_reason == "length":
                # Checked before parsing, deliberately. A cut off document that
                # happens to be balanced parses cleanly into an object missing
                # fields, and nothing downstream would ever tell you.
                raise ExtractionError("the reply was cut off before it finished")
            data = extract_json(raw)
            validate(data, schema)
            return data
        except (ExtractionError, ValidationError) as error:
            last_error = error
            if attempt == max_attempts - 1:
                break
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"That reply was not usable: {error}. Return only corrected JSON."
                    ),
                }
            )

    # The budget is spent. Raise the final error rather than a summary: it is
    # the one the model produced with the most help, so it is the one worth
    # reading in the log.
    raise last_error
