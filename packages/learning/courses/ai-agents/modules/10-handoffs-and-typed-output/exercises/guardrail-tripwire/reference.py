"""
Guardrails that can stop a run: worked solution.

The runner is unchanged from the last exercise. Everything new is at the bottom.
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




class TripwireTriggered(Exception):
    """
    A guardrail stopped the run.

    Attributes:
        result: the GuardrailResult that tripped.
        stage: "input" or "output".
        checks: every result up to and including the tripping one.
    """

    def __init__(self, result: GuardrailResult, stage: str, checks: list[GuardrailResult]):
        # The message is what a stack trace shows six weeks from now, so it
        # names the stage, the guardrail and the reason rather than the class.
        super().__init__(f"{stage} guardrail {result.name!r} tripped: {result.info}")
        self.result = result
        self.stage = stage
        self.checks = checks


def guardrail(name: str):
    """Turn a plain function into a guardrail returning a labelled GuardrailResult."""

    def decorate(check: Callable):
        @functools.wraps(check)
        def wrapper(value: str) -> GuardrailResult:
            outcome = check(value)
            # bool first: bool is a subclass of int, and one day someone returns
            # a count. Checking the exact type keeps that honest.
            if isinstance(outcome, bool):
                return GuardrailResult(name=name, tripwire=outcome)
            if isinstance(outcome, GuardrailResult):
                # Force the declared name so the trail is labelled consistently
                # even when the function left the field blank.
                return replace(outcome, name=name)
            raise TypeError(
                f"guardrail {name!r} returned {type(outcome).__name__}; "
                f"return a bool or a GuardrailResult"
            )

        wrapper._guardrail_name = name
        return wrapper

    return decorate


def guarded_run(
    agent: Agent,
    user_input: str,
    client,
    input_guardrails=(),
    output_guardrails=(),
    max_turns: int = 8,
) -> GuardedResult:
    """Run the agent with checks on the way in and on the way out."""
    checks: list[GuardrailResult] = []

    def evaluate(check: Callable, value: str, stage: str) -> None:
        outcome = check(value)
        if not isinstance(outcome, GuardrailResult):
            raise TypeError(
                f"{stage} guardrail {getattr(check, '__name__', check)!r} returned "
                f"{type(outcome).__name__}; decorate it with @guardrail(...)"
            )
        checks.append(outcome)
        if outcome.tripwire:
            raise TripwireTriggered(outcome, stage, checks)

    # Everything in this loop happens before the client is touched. That is the
    # only reason an input guardrail saves anything.
    for check in input_guardrails:
        evaluate(check, user_input, "input")

    result = run(agent, user_input, client, max_turns=max_turns)

    for check in output_guardrails:
        evaluate(check, result.final_output, "output")

    return GuardedResult(run=result, checks=checks)
