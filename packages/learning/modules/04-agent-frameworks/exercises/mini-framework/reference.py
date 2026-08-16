"""
A mini framework: reference solution.

Read this after your own attempt. The comments are about the decisions rather
than the mechanics, because the mechanics are the easy half.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, get_origin

JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class ToolSpecError(ValueError):
    """A function cannot be turned into a tool schema."""


class ToolError(Exception):
    """A tool failed in a way the model can recover from."""


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict
    result: str
    failed: bool = False


@dataclass
class AgentResult:
    answer: str
    steps: int = 0
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    tokens_used: int = 0


# A parameter line in a Google style Args: block. Deliberately simple, and the
# simplicity is the interesting part: an optional bracketed type, a colon, the
# rest of the line. A continuation line containing a colon will be read as a
# parameter, which is why every library that needs this to be right delegates
# to a real docstring parser rather than to eight lines of regex.
_PARAM = re.compile(r"^(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)$")

_ARGS_HEADERS = {"Args:", "Arguments:"}


def parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    if not doc:
        return "", {}

    # cleandoc, not strip: __doc__ carries the source indentation of every line
    # after the first, and without removing it the indentation test below is
    # measuring the file's formatting rather than the docstring's structure.
    lines = inspect.cleandoc(doc).split("\n")

    summary = ""
    for line in lines:
        if line.strip():
            summary = line.strip()
            break

    params: dict[str, str] = {}
    in_args = False
    param_indent: int | None = None
    current: str | None = None

    for line in lines:
        stripped = line.strip()
        if not in_args:
            if stripped in _ARGS_HEADERS:
                in_args = True
            continue
        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())
        if indent == 0:
            break  # Returns:, Raises:, or ordinary prose. The section is over.

        if param_indent is not None and indent > param_indent and current is not None:
            params[current] = f"{params[current]} {stripped}".strip()
            continue

        match = _PARAM.match(stripped)
        if match:
            param_indent = indent
            current = match.group(1)
            params[current] = match.group(2).strip()
        elif current is not None:
            params[current] = f"{params[current]} {stripped}".strip()

    return summary, params


def _json_type(fn_name: str, parameter: str, annotation: Any) -> str:
    # get_origin turns list[str] into list and leaves plain str alone, which is
    # the whole of this course's generics support. It stops exactly here: the
    # item type of a list, a union, a nested model. Everything past this line
    # is why frameworks reach for pydantic instead of writing this themselves.
    origin = get_origin(annotation) or annotation
    if origin in JSON_TYPES:
        return JSON_TYPES[origin]
    raise ToolSpecError(
        f"{fn_name}({parameter}) is annotated {annotation!r}, which has no JSON Schema "
        f"counterpart. Use one of {', '.join(sorted(t.__name__ for t in JSON_TYPES))}, "
        f"and express an optional value with a default rather than with a union."
    )


def describe(fn: Callable) -> dict:
    summary, documented = parse_docstring(fn.__doc__)
    if not summary:
        raise ToolSpecError(
            f"{fn.__name__} has no docstring summary. The description is the only thing "
            f"the model reads about this tool, so an empty one is an unusable schema."
        )

    try:
        hints = inspect.get_annotations(fn, eval_str=True)
    except NameError as error:
        raise ToolSpecError(f"{fn.__name__} has an annotation that will not resolve: {error}")

    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, parameter in inspect.signature(fn).parameters.items():
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            raise ToolSpecError(
                f"{fn.__name__} takes *{name}. JSON Schema describes a fixed set of named "
                f"properties, so a variadic parameter cannot be expressed at all."
            )
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            raise ToolSpecError(
                f"{fn.__name__} takes **{name}. JSON Schema describes a fixed set of named "
                f"properties, so a variadic parameter cannot be expressed at all."
            )
        if name not in hints:
            raise ToolSpecError(
                f"{fn.__name__}({name}) has no type annotation. The schema is not going to "
                f"be guessed from the parameter's name."
            )

        entry = {"type": _json_type(fn.__name__, name, hints[name])}
        description = documented.get(name)
        if description:
            entry["description"] = description
        properties[name] = entry

        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": summary,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def tool(fn: Callable) -> Callable:
    # Attach, do not wrap. The function stays the function: same name, same
    # signature, same behaviour under help(), and no extra frame in the trace
    # when a tool raises at three in the morning.
    fn.tool_schema = describe(fn)
    fn.is_tool = True
    return fn


class ToolRegistry:
    def __init__(self, tools: list[Callable] | None = None) -> None:
        # A dict preserves insertion order, so it is both the lookup table and
        # the ordering. Two structures would be two things to keep in step.
        self._tools: dict[str, Callable] = {}
        for fn in tools or []:
            self.add(fn)

    def add(self, fn: Callable) -> Callable:
        if not getattr(fn, "is_tool", False):
            tool(fn)
        name = fn.__name__
        if name in self._tools:
            raise ToolSpecError(
                f"a tool named {name!r} is already registered. The name is how the model "
                f"addresses a tool, so a second one with the same name is a coin toss."
            )
        self._tools[name] = fn
        # Returning fn is what makes @registry.add work as a decorator.
        return fn

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    @property
    def schemas(self) -> list[dict]:
        return [fn.tool_schema for fn in self._tools.values()]

    def invoke(self, name: str, arguments_json: str) -> ToolCallRecord:
        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, ValueError) as error:
            return ToolCallRecord(name, {}, f"error: arguments were not valid JSON: {error}", True)

        if not isinstance(arguments, dict):
            return ToolCallRecord(
                name, {}, "error: arguments must be a JSON object of named values", True
            )

        if name not in self._tools:
            available = ", ".join(self._tools) or "none"
            return ToolCallRecord(
                name, arguments, f"error: unknown tool {name!r}. Available: {available}", True
            )

        try:
            result = self._tools[name](**arguments)
        except ToolError as error:
            # The tool told us it failed in a way the model can work with, so
            # the message goes back as the result rather than up as a raise.
            return ToolCallRecord(name, arguments, f"error: {error}", True)
        except TypeError as error:
            # Wrong or missing arguments. The model produced them, so the model
            # is the one that has to be told.
            return ToolCallRecord(
                name, arguments, f"error: wrong arguments for {name}: {error}", True
            )

        return ToolCallRecord(name, arguments, str(result), False)


class Agent:
    def __init__(
        self,
        client,
        registry: ToolRegistry | None = None,
        system: str | None = None,
        max_steps: int = 6,
    ) -> None:
        if max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {max_steps}")
        self.client = client
        self.registry = registry if registry is not None else ToolRegistry()
        self.system = system
        self.max_steps = max_steps

    def run(self, question: str) -> AgentResult:
        # Everything below is local. Hanging any of it off self would leak one
        # run's conversation into the next, and the leak is silent: the second
        # answer is merely a bit odd rather than obviously wrong.
        messages: list[dict] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": question})

        records: list[ToolCallRecord] = []
        tokens = 0
        schemas = self.registry.schemas

        for step in range(1, self.max_steps + 1):
            response = self.client.chat.completions.create(
                model="mock", messages=messages, tools=schemas
            )
            tokens += response.usage.total_tokens
            choice = response.choices[0]

            if choice.finish_reason != "tool_calls":
                return AgentResult(
                    answer=choice.message.content or "",
                    steps=step,
                    tool_calls=records,
                    tokens_used=tokens,
                )

            # The assistant turn is recorded before its results. A tool message
            # answers an assistant message that asked for it, and providers
            # reject the request when that pairing is missing.
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
                record = self.registry.invoke(call.function.name, call.function.arguments)
                records.append(record)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": record.result}
                )

        raise MaxStepsExceeded(
            f"the agent used all {self.max_steps} model call(s) and was still asking for "
            f"tools. Tools called so far: {[r.name for r in records]}"
        )
