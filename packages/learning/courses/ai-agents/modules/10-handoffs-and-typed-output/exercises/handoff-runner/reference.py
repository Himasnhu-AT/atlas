"""
Handoffs are tool calls: worked solution.

The whole multi agent story is `current_agent = target` inside a loop that was
already there.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Callable

#: The prefix every synthetic handoff tool carries. A name that starts with this
#: and matches no target is a bug worth shouting about, not an unknown tool.
HANDOFF_PREFIX = "transfer_to_"


class UnknownHandoff(RuntimeError):
    """The model called a transfer tool that names no agent the current agent can reach."""


class MaxTurnsExceeded(RuntimeError):
    """The run used its whole turn budget without producing a final answer."""


@dataclass
class Agent:
    """
    One agent: a name, a system prompt, its tools, and who it can hand off to.

    `handoffs` is what makes this multi agent. Each entry becomes one more
    function schema in the tools list sent to the model, so from the model's
    side there is no difference between calling a tool and changing who is
    answering.
    """

    name: str
    instructions: str
    tools: list[Callable] = field(default_factory=list)
    handoffs: list["Agent"] = field(default_factory=list)


@dataclass
class RunResult:
    """
    What one run produced.

    Attributes:
        final_output: the last assistant message, or "" if it had no content.
        last_agent: the name of whichever agent was driving when the run ended.
        handoffs: (from_name, to_name) for every transfer, in the order they
            happened.
        messages: the conversation history, WITHOUT the system message. The
            system prompt changes every time the agent changes, so it is built
            fresh on each request rather than stored in the history.
        turns: how many model calls the run made.
    """

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
                    # getdoc rather than __doc__ so an indented docstring does
                    # not arrive at the provider with its leading whitespace.
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
            # The system message is rebuilt every turn from whoever is driving
            # now, and deliberately kept out of `messages`. Keeping it in the
            # history would leave the previous agent's orders in place after a
            # transfer.
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
                # Every call needs an answer, including this one. The model has
                # to see that the transfer happened, and a provider rejects a
                # request whose assistant turn has an unanswered call.
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": f"Transferred to {target.name}.",
                    }
                )
                handoffs.append((current_agent.name, target.name))
                current_agent = target
                # A handoff takes effect immediately, so anything else in this
                # batch resolves against the new agent.
                targets = {
                    handoff_tool_name(other): other for other in current_agent.handoffs
                }
                continue

            if name.startswith(HANDOFF_PREFIX):
                reachable = sorted(targets) or ["(none)"]
                raise UnknownHandoff(
                    f"{current_agent.name} tried to transfer with {name!r}, which "
                    f"names no agent it can reach. Reachable: {', '.join(reachable)}."
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": dispatch(current_agent, name, call.function.arguments),
                }
            )

    raise MaxTurnsExceeded(
        f"{max_turns} turn(s) spent and {current_agent.name} is still calling tools. "
        f"Handoffs so far: {handoffs}."
    )
