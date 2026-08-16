"""
Typed output and the retry loop.

Structured output is a tool call whose schema you generated from a type, and the
retry story is nothing more exotic than sending the validation error back as
that tool's result. You are building both halves here: the type to schema pass,
the validator, and the loop that closes the circle.

Four things to write. Everything above the divider is given.

Watch out for two details.

`from __future__ import annotations` is at the top of this file and of the test
file, which makes every annotation a STRING at runtime. `Ticket.__annotations__`
gives you `{'severity': 'int'}`, not `{'severity': <class 'int'>}`. Use
`typing.get_type_hints(...)`, which resolves them. Comparing annotation strings
works right up until someone writes `typing.Optional[str]` instead of
`str | None` and your comparison quietly stops matching.

`X | None` reports its origin as `types.UnionType` on Python 3.10 through 3.13
and as `typing.Union` on 3.14, where the two became the same object. Accept
either, or your code passes on your laptop and fails on the grader.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import types
import typing
from dataclasses import dataclass
from typing import Any

#: The name of the synthetic tool the model calls to finish. Naming it is the
#: whole trick: the model has no "return a JSON object" mode, but it does have a
#: tool calling mode, and a tool call is already a schema plus a payload.
FINAL_OUTPUT_TOOL = "final_output"


class ValidationError(ValueError):
    """
    A payload did not match the target type.

    Every problem is collected before this is raised, so the model gets one
    message listing all of them rather than one round trip per mistake. Each
    problem is a single `<field>: <message>` line.

    Attributes:
        problems: the individual lines, unjoined, for anything that wants to
            count or group them.
    """

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


class OutputValidationFailed(RuntimeError):
    """
    The model never produced a payload that validated, and the retries ran out.

    Attributes:
        last_error: the text of the final failure. This is what goes in the
            incident, so it carries the field names rather than a count.
        attempts: how many payloads were tried. A reply that came back as prose
            instead of a tool call counts as one of them: the model was asked and
            it answered, it just did not answer with a payload.
    """

    def __init__(self, last_error: str, attempts: int):
        super().__init__(f"no valid output after {attempts} attempt(s): {last_error}")
        self.last_error = last_error
        self.attempts = attempts


@dataclass
class RunContext:
    """
    What a tool gets handed alongside its own arguments.

    `deps` is whatever the caller passed to run_typed: a database handle, an
    HTTP session, a settings object. Dependency injection rather than globals,
    which is what makes a tool testable without a running system behind it.

    `retries` is how many payloads have already been rejected. A tool can read
    it, and a real system usually logs it.
    """

    deps: Any
    retries: int = 0


@dataclass
class TypedResult:
    """
    A finished typed run.

    Attributes:
        output: an instance of the requested output type, already validated.
        retries: how many payloads were rejected before this one landed.
        messages: the conversation, including the tool messages carrying every
            validation error. Worth keeping: a run with two retries in it is a
            prompt problem, and this is the evidence.
    """

    output: Any
    retries: int
    messages: list[dict]


def wants_context(function) -> bool:
    """
    Whether a tool's first parameter is annotated RunContext.

    Given to you because the introspection is fiddly and is not the point of the
    exercise. Note that it resolves the annotation rather than comparing the
    string "RunContext", for the reason in the module docstring.
    """
    parameters = list(inspect.signature(function).parameters)
    if not parameters:
        return False
    return typing.get_type_hints(function).get(parameters[0]) is RunContext


# ---------------------------------------------------------------------------
# Your work starts here.
# ---------------------------------------------------------------------------


def json_schema_for(cls) -> dict:
    """
    Turn a dataclass into a JSON Schema object, the shape a provider wants.

    Returns exactly:

        {"type": "object",
         "properties": {<field name>: <property schema>, ...},
         "required": [<fields with no default, in declaration order>],
         "additionalProperties": False}

    The property schema per annotation:

        str        -> {"type": "string"}
        int        -> {"type": "integer"}
        float      -> {"type": "number"}
        bool       -> {"type": "boolean"}
        list[str]  -> {"type": "array", "items": {"type": "string"}}
        X | None   -> the schema for X

    `X | None` says nothing about whether the field is required. Requiredness is
    decided by the default and by nothing else, so `str | None` with no default
    is still required and the model has to send it, possibly as null.

    Anything else raises TypeError naming the field and the annotation. A schema
    that silently drops a field it did not understand produces a model that
    never fills it in, and you find out from a user.

    A field declared `field(metadata={"description": "..."})` gets that string
    as a "description" key on its property. Fields without one get no
    description key at all. Descriptions are the cheapest accuracy you will ever
    buy: the model reads them, and "severity" alone means less than "severity,
    1 is lowest and 5 is highest".

    A field is required when it has neither a default nor a default_factory.
    `dataclasses.MISSING` is the sentinel for both, and `dataclasses.fields(cls)`
    gives them to you in declaration order.

    Raises:
        TypeError: the class is not a dataclass, or a field has a type this
            does not map.
    """
    raise NotImplementedError


def validate_into(cls, payload: dict) -> Any:
    """
    Build an instance of `cls` from `payload`, or raise with every problem at once.

    One `<field>: <message>` line per problem, and all of them collected before
    raising. Stopping at the first mistake costs a full round trip per mistake,
    and the model will happily fix one thing at a time forever.

    The three kinds of problem, in this wording:

        "title: missing"                         a required field is absent
        "severity: expected integer, got str"    the value is the wrong type
        "priority: unknown field"                a key that is not a field

    The order is fixed, because the model reads this list and a list that
    reshuffles between runs is harder to diff: walk the dataclass's fields in
    declaration order, reporting whichever of missing or wrong-type applies to
    each, and then report unknown keys in the order the payload had them.

    Type names in those messages are the JSON ones from json_schema_for:
    string, integer, number, boolean, array of string. The name after "got" is
    the Python one, `type(value).__name__`, because that is what the model
    actually sent.

    Rules that are easy to get wrong:
      - `bool` is a subclass of `int` in Python, so `isinstance(True, int)` is
        True. An int field must reject True, or a model that answers "true" for
        severity gets a ticket at severity 1.
      - an int is acceptable where a float is wanted, because JSON does not
        distinguish them. Convert it.
      - `X | None` accepts None as well as X.
      - a missing field that has a default is not a problem. Leave it out of the
        constructor call and let the dataclass fill it in.
      - a list[str] with one non-string element is one problem, not one per
        element.

    Raises:
        ValidationError: with every problem found.
    """
    raise NotImplementedError


def build_tool_schema(function) -> dict:
    """
    Describe an ordinary tool from its type hints and its docstring.

    Returns:
        {"type": "function",
         "function": {
             "name": <function.__name__>,
             "description": <inspect.getdoc(function) or "">,
             "parameters": {"type": "object",
                            "properties": {...},
                            "required": [...],
                            "additionalProperties": False}}}

    Property types come from the same mapping json_schema_for uses, so a tool
    taking an int is described as an integer rather than as a string. Parameters
    without a default go in `required`, in declaration order.

    A first parameter annotated RunContext is the framework's, not the model's:
    leave it out of `properties` and out of `required`. `wants_context` above
    tells you whether there is one. Advertising it would invite the model to
    fill in your database handle.

    Raises:
        TypeError: a parameter has no annotation, or one this cannot map.
    """
    raise NotImplementedError


def run_typed(
    client,
    prompt: str,
    output_type,
    tools=(),
    deps: Any = None,
    max_retries: int = 2,
) -> TypedResult:
    """
    Run until the model produces a payload that validates against `output_type`.

    The tools list sent on every call is `build_tool_schema` for each entry in
    `tools`, then one more:

        {"type": "function",
         "function": {"name": FINAL_OUTPUT_TOOL,
                      "description": <a sentence naming output_type.__name__>,
                      "parameters": json_schema_for(output_type)}}

    The loop:
      1. messages starts as [{"role": "user", "content": prompt}]
      2. call the client with messages and those tools
      3. a reply that is not a tool call means the model answered in prose when
         the only way to finish was FINAL_OUTPUT_TOOL. Raise
         OutputValidationFailed rather than returning a string that nothing
         downstream can use.
      4. append the assistant message, in the same shape as the last two
         exercises
      5. for each call in the batch, in order:
         - FINAL_OUTPUT_TOOL: parse the arguments and run validate_into.
           On success, return TypedResult(output, retries, messages).
           On ValidationError, count a retry and append
           {"role": "tool", "tool_call_id": <id>, "content": str(error)}.
           THAT is the whole retry mechanism: the model reads its own mistake as
           a tool result and tries again with the conversation intact. If the
           retry count now exceeds max_retries, raise OutputValidationFailed
           carrying that error text.
         - anything else: look the function up by __name__ in `tools`, parse its
           arguments, and call it. If wants_context(function), pass
           RunContext(deps, retries) as the FIRST positional argument and the
           parsed arguments as keywords. Otherwise pass only the keywords.
           Append the result as a tool message, stringified.
      6. loop

    max_retries counts retries, not attempts, so max_retries=2 allows three
    payloads in total and the third failure raises.

    There is deliberately no turn cap here beyond the retry budget. You built one
    in the first exercise of this module, and two competing bounds in one loop
    make it impossible to tell which one fired.

    Know what that costs outside this exercise. The retry budget only counts
    payloads, so a model that keeps calling ordinary tools and never calls
    FINAL_OUTPUT_TOOL never spends it and this loop never ends. Here the scripted
    client runs out and raises ScriptExhausted; against a real provider nothing
    stops it, and it bills you for every turn while it does not. When you combine
    the two halves of this module, keep the turn cap as well as the retry budget.

    Raises:
        OutputValidationFailed: the retries ran out, or the model replied with
            prose instead of calling the tool.
        KeyError: the model called a tool that is not in `tools`.
    """
    raise NotImplementedError
