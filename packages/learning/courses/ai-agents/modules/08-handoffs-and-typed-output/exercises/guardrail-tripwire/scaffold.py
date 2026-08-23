"""
Guardrails that can stop a run.

The runner from the last exercise is given to you complete, down to the last
line above the divider. Your work is the layer around it: a check that runs
before the client is ever touched, and a check that runs on what came back.

An input guardrail that trips must cost zero model calls. That is the whole
reason it exists, and it is the first thing the tests measure.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import functools
import inspect
import json
from dataclasses import dataclass, field, replace
from typing import Callable

HANDOFF_PREFIX = "transfer_to_"


class UnknownHandoff(RuntimeError):
    """The model called a transfer tool that names no agent the current agent can reach."""


class MaxTurnsExceeded(RuntimeError):
    """The run used its whole turn budget without producing a final answer."""


@dataclass
class Agent:
    """One agent: a name, a system prompt, its tools, and who it can hand off to."""

    name: str
    instructions: str
    tools: list[Callable] = field(default_factory=list)
    handoffs: list["Agent"] = field(default_factory=list)


@dataclass
class RunResult:
    """What one run produced. See the previous exercise for the field by field notes."""

    final_output: str
    last_agent: str
    handoffs: list[tuple[str, str]]
    messages: list[dict]
    turns: int


def handoff_tool_name(agent: Agent) -> str:
    """The name of the synthetic tool that transfers control to `agent`."""
    slug = agent.name.strip().lower().replace(" ", "_").replace("-", "_")
    return HANDOFF_PREFIX + slug


def tool_schemas(agent: Agent) -> list[dict]:
    """The tools list for this agent's turn: real tools, then handoffs."""
    schemas: list[dict] = []

    for function in agent.tools:
        properties: dict[str, dict] = {}
        required: list[str] = []
        for name, parameter in inspect.signature(function).parameters.items():
            properties[name] = {"type": "string"}
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": function.__name__,
                    "description": inspect.getdoc(function) or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )

    for target in agent.handoffs:
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": handoff_tool_name(target),
                    "description": f"Hand off to {target.name}. {target.instructions}",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        )

    return schemas


def dispatch(agent: Agent, name: str, arguments_json: str) -> str:
    """Run one ordinary tool call and return its result as a string."""
    for function in agent.tools:
        if function.__name__ == name:
            break
    else:
        raise KeyError(f"{agent.name} has no tool named {name!r}")

    arguments = json.loads(arguments_json.strip() or "{}")
    if not isinstance(arguments, dict):
        raise ValueError(f"arguments for {name!r} must be a JSON object")

    return str(function(**arguments))


def run(agent: Agent, user_input: str, client, max_turns: int = 8) -> RunResult:
    """Drive the loop until an agent answers without calling a tool."""
    if max_turns < 1:
        raise ValueError(f"max_turns must be at least 1, got {max_turns}")

    current_agent = agent
    messages: list[dict] = [{"role": "user", "content": user_input}]
    handoffs: list[tuple[str, str]] = []

    for turn in range(1, max_turns + 1):
        response = client.chat.completions.create(
            model="mock",
            messages=[{"role": "system", "content": current_agent.instructions}] + messages,
            tools=tool_schemas(current_agent),
        )
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            return RunResult(
                final_output=choice.message.content or "",
                last_agent=current_agent.name,
                handoffs=handoffs,
                messages=messages,
                turns=turn,
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

        targets = {handoff_tool_name(target): target for target in current_agent.handoffs}

        for call in choice.message.tool_calls:
            name = call.function.name
            if name in targets:
                target = targets[name]
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": f"Transferred to {target.name}.",
                    }
                )
                handoffs.append((current_agent.name, target.name))
                current_agent = target
                targets = {
                    handoff_tool_name(other): other for other in current_agent.handoffs
                }
                continue

            if name.startswith(HANDOFF_PREFIX):
                raise UnknownHandoff(f"{current_agent.name} cannot transfer with {name!r}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": dispatch(current_agent, name, call.function.arguments),
                }
            )

    raise MaxTurnsExceeded(f"{max_turns} turn(s) spent with no final answer")


@dataclass
class GuardrailResult:
    """
    What one guardrail decided.

    Attributes:
        name: the name the guardrail was declared with, not the function's.
        tripwire: True means stop the run. False means carry on.
        info: why, in a sentence. This is what an operator reads in the log and
            what a caller may show the user, so put the offending value in it.
    """

    name: str
    tripwire: bool
    info: str = ""


@dataclass
class GuardedResult:
    """
    A completed run plus the trail of every check that passed on the way.

    Only produced when nothing tripped. A trip raises instead, because a caller
    that has to remember to inspect a flag will forget on the day it matters.
    """

    run: RunResult
    checks: list[GuardrailResult]


# ---------------------------------------------------------------------------
# Your work starts here.
# ---------------------------------------------------------------------------


class TripwireTriggered(Exception):
    """
    A guardrail stopped the run.

    Write __init__ so that it stores the three attributes below and calls
    super().__init__ with a message naming the stage, the guardrail, and its
    info, in that order. The message is what a stack trace shows, and "tripwire
    triggered" on its own tells an on-call engineer nothing.

    Attributes:
        result: the GuardrailResult that tripped.
        stage: "input" or "output". Which one it was decides what you do next:
            an input trip means the user asked for something you refuse, an
            output trip means your own agent produced something you refuse, and
            those are different conversations to have.
        checks: every result up to and including the tripping one. Nothing after
            it, because evaluation stops at the first trip.
    """

    def __init__(self, result: GuardrailResult, stage: str, checks: list[GuardrailResult]):
        raise NotImplementedError


def guardrail(name: str):
    """
    Turn a plain function into a guardrail.

    The decorated function takes one string and returns either a bool or a
    GuardrailResult. Returning True means TRIPPED, which reads backwards the
    first time and is the convention the real SDKs use: the function answers
    "did the tripwire fire", not "is this fine".

        @guardrail("no_secrets")
        def no_secrets(value: str) -> bool:
            return "sk-" in value

        @guardrail("length")
        def length(value: str) -> GuardrailResult:
            return GuardrailResult("", len(value) > 500, f"{len(value)} characters")

    The wrapper you return must:
      - call the wrapped function with the value
      - turn a bool into GuardrailResult(name=name, tripwire=<the bool>)
      - take a returned GuardrailResult and force its `name` to `name`, so the
        trail is always labelled with the declared name even when the function
        left it blank. `dataclasses.replace` is imported for you.
      - raise TypeError on anything else, naming what came back
      - stay directly callable and keep the original __name__, so a unit test
        can call the guardrail on a string without a run. functools.wraps does
        the second part.

    Also set `_guardrail_name` on the wrapper. Frameworks hang metadata on the
    function object like this so a registry can list what is installed without
    calling anything.
    """
    raise NotImplementedError


def guarded_run(
    agent: Agent,
    user_input: str,
    client,
    input_guardrails=(),
    output_guardrails=(),
    max_turns: int = 8,
) -> GuardedResult:
    """
    Run the agent with checks on the way in and on the way out.

    Order, and it matters:
      1. every input guardrail against `user_input`, in the order given, BEFORE
         the client is touched. The first one whose tripwire is set raises
         TripwireTriggered(result, "input", checks) and the model is never
         called. A guardrail that trips after the model call has already saved
         you nothing.
      2. run(agent, user_input, client, max_turns=max_turns)
      3. every output guardrail against `result.final_output`, in the order
         given. The first trip raises TripwireTriggered(result, "output", ...).

    `checks` accumulates across both stages and is handed to the exception, so
    the trail always ends with the result that tripped and contains nothing
    after it.

    A guardrail that raises anything other than TripwireTriggered is left alone
    to propagate. A check that crashes is a bug in the check, and swallowing it
    into a tripwire would turn a broken regex into a silent policy decision.

    Raises:
        TripwireTriggered: a guardrail stopped the run.
        TypeError: a guardrail returned something that is not a GuardrailResult,
            which almost always means it was never decorated with @guardrail.

    Returns:
        GuardedResult(run=<the RunResult>, checks=<every result, in order>).
    """
    raise NotImplementedError
