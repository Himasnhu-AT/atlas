"""
Tool schemas: worked solution.

Build the schema the model reads from the function your code runs, then refuse
anything that does not match it before the function is reached.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

SECTION_HEADING = re.compile(r"^\s*[A-Z][A-Za-z ]*:\s*$")
PARAMETER_LINE = re.compile(r"^\s*(\w+)\s*:\s*(\S.*)$")


class ToolError(Exception):
    """A tool call could not be honoured. The message is written for the model."""


@dataclass(frozen=True)
class Tool:
    """The schema the model sees and the function your code runs, together."""

    fn: Callable
    schema: dict


def split_docstring(docstring: str | None) -> tuple[str, dict[str, str]]:
    """Summary text and per-parameter descriptions from a Google style docstring."""
    if not docstring or not docstring.strip():
        return "", {}

    summary: list[str] = []
    descriptions: dict[str, str] = {}
    current: str | None = None
    in_args = False

    # cleandoc, not textwrap.dedent. The first line of a docstring has no
    # indentation of its own, so dedent finds a common prefix of "" and leaves
    # every continuation line indented.
    for line in inspect.cleandoc(docstring).splitlines():
        stripped = line.strip()

        if not in_args:
            if stripped == "Args:":
                in_args = True
            elif stripped:
                summary.append(stripped)
            continue

        if SECTION_HEADING.match(line):
            break

        match = PARAMETER_LINE.match(line)
        if match:
            current = match.group(1)
            descriptions[current] = match.group(2).strip()
        elif stripped and current is not None:
            # A wrapped description. One parameter, one string.
            descriptions[current] = f"{descriptions[current]} {stripped}"

    return " ".join(summary), descriptions


def _resolved_annotations(fn: Callable) -> dict[str, Any]:
    """
    The real annotation objects, not the strings PEP 563 leaves behind.

    eval_str=True re-evaluates each annotation in the function's own globals.
    It can raise on a name that is not importable at runtime, and a schema
    builder that dies on one exotic annotation is worse than one that calls it
    a string, so the failure is absorbed.
    """
    try:
        return inspect.get_annotations(fn, eval_str=True)
    except Exception:
        return dict(getattr(fn, "__annotations__", {}))


def build_schema(fn: Callable, enums: dict[str, list[str]] | None = None) -> dict:
    """Build an OpenAI style tool schema by inspecting a function."""
    enums = enums or {}
    summary, descriptions = split_docstring(fn.__doc__)
    annotations = _resolved_annotations(fn)

    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, parameter in inspect.signature(fn).parameters.items():
        if name == "self":
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            # JSON Schema cannot express either, and a schema that implies the
            # model may pass anything is a schema that stops constraining.
            continue

        properties[name] = {
            "type": JSON_TYPES.get(annotations.get(name), "string"),
            "description": descriptions.get(name, ""),
        }
        if name in enums:
            properties[name]["enum"] = list(enums[name])
        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    unknown = sorted(set(enums) - set(properties))
    if unknown:
        raise ValueError(
            f"{fn.__name__} has no parameter named {unknown[0]!r}, so the enum for it "
            f"would never reach the model. Parameters: {', '.join(properties) or 'none'}"
        )

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": summary,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                # Providers that offer a strict mode require this key and refuse
                # a schema without it. It costs nothing when strict mode is off.
                "additionalProperties": False,
            },
        },
    }


def build_registry(
    functions: list[Callable],
    enums: dict[str, dict[str, list[str]]] | None = None,
) -> dict[str, Tool]:
    """Index functions by name, building each one's schema as you go."""
    enums = enums or {}
    registry: dict[str, Tool] = {}
    for fn in functions:
        name = fn.__name__
        if name in registry:
            raise ValueError(
                f"two tools are called {name!r}. The name is the only handle the model "
                f"has, so one of them could never be called."
            )
        registry[name] = Tool(fn=fn, schema=build_schema(fn, enums.get(name)))
    return registry


def _type_matches(json_type: str, value: Any) -> bool:
    """One JSON Schema type check, with the bool trap handled."""
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "integer":
        # isinstance(True, int) is True in Python, which would let `true` land
        # in a parameter that wanted a count.
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        # JSON has a single number type, so a model that means 2.0 writes 2.
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    return True


def validate_arguments(schema: dict, arguments: dict) -> dict:
    """Check a parsed argument dict against a tool schema."""
    function = schema["function"]
    name = function["name"]
    parameters = function["parameters"]
    properties = parameters["properties"]
    required = parameters.get("required", [])

    missing = [key for key in required if key not in arguments]
    if missing:
        raise ToolError(
            f"{name} is missing required argument(s): {', '.join(missing)}. "
            f"Required: {', '.join(required) or 'none'}"
        )

    unexpected = [key for key in arguments if key not in properties]
    if unexpected:
        raise ToolError(
            f"{name} does not accept argument(s): {', '.join(sorted(unexpected))}. "
            f"Accepted: {', '.join(properties) or 'none'}"
        )

    for key, value in arguments.items():
        declared = properties[key]
        if not _type_matches(declared.get("type", "string"), value):
            raise ToolError(
                f"{name}: argument {key!r} should be of type "
                f"{declared.get('type', 'string')}, got {type(value).__name__}"
            )
        allowed = declared.get("enum")
        if allowed is not None and value not in allowed:
            raise ToolError(
                f"{name}: argument {key!r} must be one of "
                f"{', '.join(repr(option) for option in allowed)}, got {value!r}"
            )

    return arguments


def dispatch(registry: dict[str, Tool], name: str, arguments_json: str) -> str:
    """Run one tool call from the model, after proving it is well formed."""
    tool = registry.get(name)
    if tool is None:
        available = ", ".join(sorted(registry)) or "none"
        raise ToolError(f"unknown tool: {name!r}. Available tools: {available}")

    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, ValueError) as error:
        raise ToolError(f"arguments for {name} were not valid JSON: {error}") from error

    if not isinstance(arguments, dict):
        raise ToolError(
            f"arguments for {name} must be a JSON object, got "
            f"{type(arguments).__name__}"
        )

    validate_arguments(tool.schema, arguments)

    # Whatever the tool raises from here is its own failure, not a malformed
    # call, and it travels up to a caller that knows the difference.
    return str(tool.fn(**arguments))
