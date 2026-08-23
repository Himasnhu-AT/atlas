"""
Typed output and the retry loop: worked solution.

The shape to notice: `_property_schema` is the single place that knows how a
Python annotation becomes a JSON type, and both the output schema and the tool
schemas go through it. One mapping, so a tool and an output can never disagree
about what an int is.
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
        attempts: how many payloads were tried.
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




def _optional_of(annotation) -> tuple[Any, bool]:
    """
    Split `X | None` into (X, True). Anything else comes back as (it, False).

    `types.UnionType` is what `X | None` reports on 3.10 through 3.13, and
    `typing.Union` is what `typing.Optional[X]` reports. On 3.14 they are the
    same object. Checking both is the portable version.
    """
    origin = typing.get_origin(annotation)
    if origin is types.UnionType or origin is typing.Union:
        present = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(present) == 1:
            return present[0], True
        raise TypeError(f"cannot map the union {annotation!r} to one JSON type")
    return annotation, False


def _property_schema(annotation, where: str) -> dict:
    """The JSON Schema property for one annotation. The only type mapping in the file."""
    inner, _ = _optional_of(annotation)
    if inner is str:
        return {"type": "string"}
    if inner is bool:
        return {"type": "boolean"}
    if inner is int:
        return {"type": "integer"}
    if inner is float:
        return {"type": "number"}
    if typing.get_origin(inner) is list and typing.get_args(inner) == (str,):
        return {"type": "array", "items": {"type": "string"}}
    raise TypeError(f"{where}: cannot map {annotation!r} to a JSON schema type")


def _json_type_name(annotation) -> str:
    """What to call a type when telling the model it sent the wrong one."""
    schema = _property_schema(annotation, "value")
    return "array of string" if schema["type"] == "array" else schema["type"]


def _is_required(field: dataclasses.Field) -> bool:
    return field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING


def json_schema_for(cls) -> dict:
    """Turn a dataclass into a JSON Schema object."""
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    # get_type_hints rather than __annotations__, because `from __future__
    # import annotations` leaves the latter full of strings.
    hints = typing.get_type_hints(cls)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for field in dataclasses.fields(cls):
        schema = _property_schema(hints[field.name], f"{cls.__name__}.{field.name}")
        description = field.metadata.get("description")
        if description:
            schema["description"] = description
        properties[field.name] = schema
        if _is_required(field):
            required.append(field.name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _coerce(annotation, value, name: str) -> tuple[Any, str | None]:
    """Check one value against one annotation. Returns (value, problem or None)."""
    inner, optional = _optional_of(annotation)

    if value is None:
        if optional:
            return None, None
        return None, f"{name}: expected {_json_type_name(inner)}, got NoneType"

    if inner is bool:
        acceptable = isinstance(value, bool)
    elif inner is int:
        # bool is a subclass of int, so this has to be explicit. Without it,
        # True arrives as severity 1 and nothing complains.
        acceptable = isinstance(value, int) and not isinstance(value, bool)
    elif inner is float:
        acceptable = isinstance(value, (int, float)) and not isinstance(value, bool)
        if acceptable:
            value = float(value)  # JSON has one number type; 3 is a valid float
    elif inner is str:
        acceptable = isinstance(value, str)
    else:
        acceptable = isinstance(value, list) and all(isinstance(item, str) for item in value)

    if not acceptable:
        return None, f"{name}: expected {_json_type_name(inner)}, got {type(value).__name__}"
    return value, None


def validate_into(cls, payload: dict) -> Any:
    """Build an instance of `cls` from `payload`, collecting every problem first."""
    if not dataclasses.is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    hints = typing.get_type_hints(cls)
    fields = {field.name: field for field in dataclasses.fields(cls)}
    problems: list[str] = []
    arguments: dict[str, Any] = {}

    for name, field in fields.items():
        if name not in payload:
            if _is_required(field):
                problems.append(f"{name}: missing")
            continue  # a default is not a problem; let the dataclass apply it
        value, problem = _coerce(hints[name], payload[name], name)
        if problem is not None:
            problems.append(problem)
        else:
            arguments[name] = value

    for key in payload:
        if key not in fields:
            problems.append(f"{key}: unknown field")

    if problems:
        raise ValidationError(problems)
    return cls(**arguments)


def build_tool_schema(function) -> dict:
    """Describe an ordinary tool from its type hints and its docstring."""
    hints = typing.get_type_hints(function)
    parameters = list(inspect.signature(function).parameters.items())
    if wants_context(function):
        parameters = parameters[1:]  # the framework's argument, not the model's

    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, parameter in parameters:
        if name not in hints:
            raise TypeError(f"{function.__name__}({name}) has no type annotation")
        properties[name] = _property_schema(hints[name], f"{function.__name__}({name})")
        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": function.__name__,
            "description": inspect.getdoc(function) or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def run_typed(
    client,
    prompt: str,
    output_type,
    tools=(),
    deps: Any = None,
    max_retries: int = 2,
) -> TypedResult:
    """Run until the model produces a payload that validates against `output_type`."""
    by_name = {function.__name__: function for function in tools}
    schemas = [build_tool_schema(function) for function in tools]
    schemas.append(
        {
            "type": "function",
            "function": {
                "name": FINAL_OUTPUT_TOOL,
                "description": (
                    f"Return the final answer as a {output_type.__name__}. "
                    f"Call this once, when you have everything you need."
                ),
                "parameters": json_schema_for(output_type),
            },
        }
    )

    messages: list[dict] = [{"role": "user", "content": prompt}]
    retries = 0

    while True:
        response = client.chat.completions.create(
            model="mock", messages=messages, tools=schemas
        )
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            raise OutputValidationFailed(
                f"the model replied with prose instead of calling {FINAL_OUTPUT_TOOL}",
                retries + 1,
            )

        messages.append(
            {
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in choice.message.tool_calls
                ],
            }
        )

        for call in choice.message.tool_calls:
            arguments = json.loads(call.function.arguments.strip() or "{}")

            if call.function.name == FINAL_OUTPUT_TOOL:
                try:
                    output = validate_into(output_type, arguments)
                except ValidationError as error:
                    retries += 1
                    # The error text IS the retry. It goes back as this call's
                    # result, so the model reads its own mistake in place and
                    # tries again with the conversation intact.
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": str(error),
                        }
                    )
                    if retries > max_retries:
                        raise OutputValidationFailed(str(error), retries) from error
                    continue
                return TypedResult(output=output, retries=retries, messages=messages)

            function = by_name[call.function.name]
            if wants_context(function):
                result = function(RunContext(deps, retries), **arguments)
            else:
                result = function(**arguments)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": str(result)}
            )
