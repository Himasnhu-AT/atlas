"""
Compiling a spec into an agent: reference solution.

Read this after your own attempt. Most of the interesting decisions are about
where a failure is allowed to happen, and the answer is always "earlier".
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Any, Callable

MAX_STEP_BUDGET = 50

SPEC_KEYS = ("name", "system", "tools", "max_steps")

REQUIRED_KEYS = ("name", "system")


class SpecError(ValueError):
    """A spec cannot be turned into an agent."""


class ToolError(Exception):
    """A tool failed in a way the model can recover from."""


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system: str
    tools: tuple[str, ...] = ()
    max_steps: int = 6


class ToolRegistry:
    """The registry from the mini framework exercise, trimmed."""

    def __init__(self, tools: list[Callable] | None = None) -> None:
        self._tools: dict[str, Callable] = {fn.__name__: fn for fn in tools or []}

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Callable | None:
        return self._tools.get(name)

    def subset(self, names: tuple[str, ...] | list[str]) -> "ToolRegistry":
        chosen = ToolRegistry()
        for name in names:
            fn = self._tools.get(name)
            if fn is None:
                raise KeyError(name)
            chosen._tools[name] = fn
        return chosen

    @property
    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": (fn.__doc__ or "").strip().split("\n")[0],
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
            for name, fn in self._tools.items()
        ]

    def invoke(self, name: str, arguments_json: str) -> str:
        try:
            arguments = json.loads(arguments_json)
        except (json.JSONDecodeError, ValueError):
            return "error: arguments were not valid JSON"
        if not isinstance(arguments, dict):
            return "error: arguments must be a JSON object"
        fn = self._tools.get(name)
        if fn is None:
            return f"error: unknown tool {name!r}"
        try:
            return str(fn(**arguments))
        except ToolError as failure:
            return f"error: {failure}"
        except TypeError as failure:
            return f"error: wrong arguments for {name}: {failure}"


class Agent:
    """The agent from the mini framework exercise."""

    def __init__(
        self,
        client,
        registry: ToolRegistry | None = None,
        system: str | None = None,
        max_steps: int = 6,
        name: str = "agent",
    ) -> None:
        if max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {max_steps}")
        self.client = client
        self.registry = registry if registry is not None else ToolRegistry()
        self.system = system
        self.max_steps = max_steps
        self.name = name

    def run(self, question: str) -> str:
        messages: list[dict] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": question})
        schemas = self.registry.schemas

        for _ in range(self.max_steps):
            response = self.client.chat.completions.create(
                model="mock", messages=messages, tools=schemas
            )
            choice = response.choices[0]
            if choice.finish_reason != "tool_calls":
                return choice.message.content or ""

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
                result = self.registry.invoke(call.function.name, call.function.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        raise MaxStepsExceeded(f"{self.name} used all {self.max_steps} model call(s)")


def spec_from_dict(data: Any) -> AgentSpec:
    if not isinstance(data, dict):
        raise SpecError(f"a spec is a mapping of {', '.join(SPEC_KEYS)}, got {type(data).__name__}")

    unknown = [key for key in data if key not in SPEC_KEYS]
    if unknown:
        # First, deliberately. A misspelled key is the failure that otherwise
        # produces an agent with no instructions and a confusing transcript.
        raise SpecError(
            f"unknown key {unknown[0]!r}. A spec takes: {', '.join(SPEC_KEYS)}."
        )

    for key in REQUIRED_KEYS:
        if key not in data:
            raise SpecError(f"missing required key {key!r}")

    for key in REQUIRED_KEYS:
        if not isinstance(data[key], str):
            raise SpecError(f"{key!r} must be a string, got {type(data[key]).__name__}")

    tools = data.get("tools", ())
    if not isinstance(tools, (list, tuple)):
        raise SpecError(f"'tools' must be a list of names, got {type(tools).__name__}")
    if not all(isinstance(name, str) for name in tools):
        raise SpecError("'tools' must be a list of names, and every entry must be a string")

    max_steps = data.get("max_steps", 6)
    # bool is a subclass of int, and True as a step budget is a config file
    # mistake rather than a budget of one.
    if isinstance(max_steps, bool) or not isinstance(max_steps, int):
        raise SpecError(f"'max_steps' must be an integer, got {type(max_steps).__name__}")

    return AgentSpec(
        name=data["name"],
        system=data["system"],
        tools=tuple(tools),
        max_steps=max_steps,
    )


def validate_spec(spec: AgentSpec, registry: ToolRegistry) -> None:
    if not spec.name.strip():
        raise SpecError("'name' must not be blank: it is what a trace will call this agent")

    if not spec.system.strip():
        raise SpecError(
            f"{spec.name}: 'system' must not be blank. An agent with no instructions is "
            f"a model with tools attached."
        )

    if not 1 <= spec.max_steps <= MAX_STEP_BUDGET:
        raise SpecError(
            f"{spec.name}: 'max_steps' must be between 1 and {MAX_STEP_BUDGET}, "
            f"got {spec.max_steps}"
        )

    seen: set[str] = set()
    for name in spec.tools:
        if name in seen:
            raise SpecError(f"{spec.name}: tool {name!r} is listed twice")
        seen.add(name)

    known = registry.names
    for name in spec.tools:
        if name in known:
            continue
        # difflib is stdlib and deterministic. The suggestion is the difference
        # between a five second fix and a grep through the codebase.
        close = difflib.get_close_matches(name, known, n=1)
        suggestion = f", did you mean {close[0]!r}" if close else ""
        raise SpecError(
            f"{spec.name}: unknown tool {name!r}{suggestion}. "
            f"Registered: {', '.join(known) or 'none'}."
        )


def build_agent(spec: AgentSpec, registry: ToolRegistry, client) -> Agent:
    # Validation first, and nothing above this line touches the client. That
    # ordering is the entire claim the exercise makes: a bad spec costs an
    # exception, not a model call.
    validate_spec(spec, registry)

    return Agent(
        client,
        # Only what the spec named, in the order it named it. Handing over the
        # whole registry would make the tools list documentation rather than a
        # boundary.
        registry=registry.subset(spec.tools),
        system=spec.system,
        max_steps=spec.max_steps,
        name=spec.name,
    )


def diff_specs(old: AgentSpec, new: AgentSpec) -> list[str]:
    lines: list[str] = []

    if old.name != new.name:
        lines.append(f"name: {old.name!r} -> {new.name!r}")

    if old.system != new.system:
        # One word on purpose. See the docstring: a prompt wants a text diff,
        # and pretending a summary can be one helps nobody.
        lines.append("system: changed")

    added = sorted(set(new.tools) - set(old.tools))
    removed = sorted(set(old.tools) - set(new.tools))
    if added:
        lines.append(f"tools added: {', '.join(added)}")
    if removed:
        lines.append(f"tools removed: {', '.join(removed)}")
    if not added and not removed and old.tools != new.tools:
        lines.append("tools reordered")

    if old.max_steps != new.max_steps:
        lines.append(f"max_steps: {old.max_steps} -> {new.max_steps}")

    return lines
