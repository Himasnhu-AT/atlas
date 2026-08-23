"""
Structured output.

Get an object out of whatever a model actually sent, check it against a schema,
and retry with the error fed back into the conversation. This is the path you
need whether or not your provider offers a structured mode, because no decoder
checks that the values make sense.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations


class ExtractionError(Exception):
    """No usable JSON object could be recovered from the reply."""


class ValidationError(Exception):
    """The parsed object did not match the schema."""


def find_json_object(text: str) -> str:
    """
    Return the first complete, brace balanced JSON object in `text`.

    A regular expression cannot do this correctly. Braces nest, and a brace
    inside a string literal must not be counted. Scan the characters instead,
    tracking whether you are inside a string and whether the previous character
    was a backslash, and count depth only outside strings.

    Args:
        text: any text that might contain a JSON object.

    Returns:
        The substring from the first "{" to its matching "}", inclusive.

    Raises:
        ExtractionError: there is no "{", or it never closes. A document that
            never closes is usually a reply that was cut off, so say so.

    Examples:
        >>> find_json_object('Sure! {"a": 1} hope that helps')
        '{"a": 1}'
        >>> find_json_object('{"note": "a } inside a string", "b": 2}')
        '{"note": "a } inside a string", "b": 2}'
    """
    raise NotImplementedError


def extract_json(text: str) -> dict:
    """
    Pull an object out of a model reply, however it was wrapped.

    Try these in order and stop at the first that works:
      1. json.loads on the whole stripped string
      2. strip one markdown code fence (``` or ```json) and retry
      3. find_json_object, then json.loads on that

    The order is deliberate. The common case is a clean reply, and paying for a
    character scan on every call to handle the uncommon one is backwards.

    Args:
        text: the raw reply content.

    Returns:
        The parsed object.

    Raises:
        ExtractionError: none of the three produced a dict. A JSON value that
            parses but is not an object, such as a list or a bare number, is
            also an error: the caller asked for named fields.
    """
    raise NotImplementedError


def validate(data: dict, schema: dict) -> None:
    """
    Check a parsed object against a small schema.

    The schema maps a field name to a spec dict:
        {"type": "string" | "integer" | "number" | "boolean" | "array" | "object",
         "required": bool,          # defaults to True
         "enum": [...],             # optional, the allowed values
         "nullable": bool}          # defaults to False

    Rules:
      - A required field that is absent is an error.
      - An absent optional field is fine.
      - A value of None is fine only when nullable is True, and it skips the
        type and enum checks when it is allowed.
      - A type mismatch is an error. In Python `bool` is a subclass of `int`,
        so a naive isinstance check accepts True as an integer. It is not one,
        and a model that answers a quantity with `true` should fail here.
      - An integer satisfies {"type": "number"}. A float does not satisfy
        {"type": "integer"}.
      - A value outside `enum` is an error.
      - Fields not in the schema are ignored. You are checking what you consume.

    Raises:
        ValidationError: on the first problem, with a message naming the field
            and what was wrong. That message is fed back to the model on a
            retry, so "quantity: expected integer, got str" earns its keep and
            "invalid" does not. Check fields in the schema's order so the
            message is predictable.
    """
    raise NotImplementedError


def extract_with_retry(
    client,
    prompt: str,
    schema: dict,
    *,
    max_attempts: int = 3,
) -> dict:
    """
    Ask for structured data, retrying with the error fed back.

    Each attempt:
      - call client.chat.completions.create(model="mock", messages=messages)
      - if choices[0].finish_reason is "length" the reply was cut off, so treat
        it as an ExtractionError without trying to parse it. A truncated
        document that happens to close its braces parses into an object missing
        half its fields, which is the version that reaches production.
      - otherwise run extract_json then validate
      - on success return the object

    On failure, append the assistant's raw reply as
    {"role": "assistant", "content": raw} and then
    {"role": "user", "content": f"That reply was not usable: {error}. "
                                "Return only corrected JSON."}
    and go round again. Both appends matter: the bad reply gives the model
    something concrete to correct, and the error gives it the specific
    complaint rather than a vague nudge.

    Args:
        client: anything with the chat completions shape. mockllm's MockClient
            is one, and so is a real provider's.
        prompt: the first user message.
        schema: passed straight to validate.
        max_attempts: TOTAL model calls, not retries after the first.
            max_attempts=1 means one call and no retry. That is the number that
            shows up on the bill and in the latency, so it is the number to
            budget in.

    Returns:
        The first object that parses and validates.

    Raises:
        ValueError: max_attempts < 1.
        ExtractionError or ValidationError: the error from the FINAL attempt,
            once the budget is spent. Raise the last one rather than a summary,
            because the last one is what the model produced with the most help.
    """
    raise NotImplementedError
