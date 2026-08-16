"""
Compiling a spec into an agent.

An agent stops being code you wrote and becomes a record something else runs.
That buys you inspection, diffing and generated variants. It costs you the
moment you need behaviour the schema cannot express.

`ToolRegistry` and `Agent` below are given, unchanged from the earlier
exercises. You write the four functions that turn a dict of configuration into
one of those agents, and the one that says how two specs differ.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Any, Callable

#: The largest step budget a spec may ask for. A number in a config file has
#: nobody reviewing it, so the ceiling lives in code.
MAX_STEP_BUDGET = 50

#: Every key a spec may carry. Anything else is a typo, and saying so is most
#: of the value of validating configuration at all.
SPEC_KEYS = ("name", "system", "tools", "max_steps")

#: The keys without a default.
REQUIRED_KEYS = ("name", "system")


class SpecError(ValueError):
    """
    A spec cannot be turned into an agent.

    Every message this carries names the field and says what would have been
    right. The person reading it is holding a config file, not a debugger.
    """


class ToolError(Exception):
    """A tool failed in a way the model can recover from."""


class MaxStepsExceeded(Exception):
    """The agent spent its whole step budget without producing an answer."""


@dataclass(frozen=True)
class AgentSpec:
    """
    An agent as data. Given complete.

    Frozen and holding a tuple rather than a list, so a spec can be compared,
    hashed, put in a set of variants, and handed to two builders without either
    of them editing the other's copy.

    Attributes:
        name: what this agent is called, for traces and error messages.
        system: the standing instructions.
        tools: the tool names this agent may call, in the order they will be
            offered to the model.
        max_steps: model calls per run.
    """

    name: str
    system: str
    tools: tuple[str, ...] = ()
    max_steps: int = 6


class ToolRegistry:
    """The registry from the mini framework exercise, trimmed. Given complete."""

    def __init__(self, tools: list[Callable] | None = None) -> None:
        self._tools: dict[str, Callable] = {fn.__name__: fn for fn in tools or []}

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Callable | None:
        return self._tools.get(name)

    def subset(self, names: tuple[str, ...] | list[str]) -> "ToolRegistry":
        """A new registry holding only `names`, in the order given."""
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
    """The agent from the mini framework exercise. Given complete."""

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
    """
    Turn a plain dict, as parsed from JSON or YAML, into an AgentSpec.

    This is the shape checking half, and nothing here knows what a tool is.

    Args:
        data: the parsed configuration. Not necessarily a dict, because the
            file it came from was written by a person.

    Returns:
        An AgentSpec. `tools` becomes a tuple. `max_steps` defaults to 6 and
        `tools` to empty.

    Raises:
        SpecError: `data` is not a dict, a key in REQUIRED_KEYS is missing, a
            key is not in SPEC_KEYS, or a value has the wrong type. Name the
            offending key in every message, and for an unknown key list the
            ones that exist. Watch the type check on max_steps: bool is a
            subclass of int in Python, and `max_steps: true` in a config file
            is a mistake rather than a budget of one.

    Rejecting an unknown key is the check that earns its keep. Nobody spells
    "system" wrong, but "prompt" and "tool" are what people write, and a spec
    loader that ignores keys it does not recognise will silently run an agent
    with no instructions and no tools.
    """
    raise NotImplementedError


def validate_spec(spec: AgentSpec, registry: ToolRegistry) -> None:
    """
    Check a spec against the world it will run in. Returns None, or raises.

    Where spec_from_dict asks whether the shape is right, this asks whether the
    contents mean anything: a name and instructions that are not blank, a step
    budget between 1 and MAX_STEP_BUDGET, no tool listed twice, and every tool
    present in `registry`.

    Raises:
        SpecError: the first problem found, named precisely. For an unknown
            tool, name it and, when difflib finds a close match among the
            registry's names, suggest it. "unknown tool 'refunds'" costs
            somebody ten minutes; "unknown tool 'refunds', did you mean
            'refund'" costs them none.

    Every one of these could be left to fail at run time. The reason it is not
    is the whole argument for the declarative shape: a spec that fails here
    fails on the line that loaded the file, before a single token is bought.
    """
    raise NotImplementedError


def build_agent(spec: AgentSpec, registry: ToolRegistry, client) -> Agent:
    """
    Compile a spec into a runnable Agent.

    Validate first. Then give the agent a registry holding only the tools the
    spec names, in the order the spec names them, and nothing else. An agent
    that can see every tool in the process is an agent whose spec is a comment
    rather than a boundary.

    Args:
        spec: what to build.
        registry: every tool that exists.
        client: the model client the agent will use.

    Returns:
        An Agent whose `name`, `system` and `max_steps` come from the spec.

    Raises:
        SpecError: whatever validate_spec raises, unchanged and before the
            client is touched.
    """
    raise NotImplementedError


def diff_specs(old: AgentSpec, new: AgentSpec) -> list[str]:
    """
    Say how two specs differ, in lines a person can read in a review.

    Returns:
        One string per difference, always in this order, and an empty list when
        the specs are equal:

            name: 'triage' -> 'router'
            system: changed
            tools added: escalate, refund
            tools removed: lookup
            tools reordered
            max_steps: 6 -> 8

        Added and removed names are sorted alphabetically. "tools reordered"
        appears only when the same names are present in a different order, and
        the order is worth reporting because it is the order the model sees
        them in.

    The system prompt gets one word rather than a before and after. A four
    hundred word prompt rendered into a list of one line differences is
    unreadable, and the thing that reads it well is a text diff, which
    difflib.unified_diff already gives you. Knowing where to stop is the point:
    a summary that tries to be a diff is worse at both jobs.

    This function is the argument for the whole declarative shape. Two agents
    written as code differ by a code review; two agents written as data differ
    by six lines you can put in a pull request description.
    """
    raise NotImplementedError
