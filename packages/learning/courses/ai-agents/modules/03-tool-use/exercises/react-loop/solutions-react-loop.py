"""
The ReAct loop, from scratch: worked solution.

Call, act, observe, repeat, and stop for a reason you can name.
"""

from __future__ import annotations

import json
from typing import Any, Callable


class MaxStepsExceeded(Exception):
    """The step budget ran out before the model produced a final answer."""

    def __init__(self, steps: int, messages: list[dict]) -> None:
        super().__init__(
            f"the agent used all {steps} model calls without producing an answer"
        )
        self.steps = steps
        # The transcript is the diagnosis. Without it you know the agent looped
        # and nothing about what it was looping on.
        self.messages = messages


class TruncatedAnswer(Exception):
    """The model was cut off by its output limit part way through a reply."""


class ToolError(Exception):
    """A tool call could not be honoured."""


def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression.

    Args:
        expression: The arithmetic to evaluate, for example "(19 * 42) - 8".
    """
    allowed = set("0123456789.+-*/() ")
    if not expression or any(character not in allowed for character in expression):
        return f"error: expression contains disallowed characters: {expression!r}"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as error:
        return f"error: {error}"


def lookup_population(city: str) -> dict:
    """Look up the population of a city.

    Args:
        city: City name on its own, in English.
    """
    table = {"paris": 2_102_650, "tokyo": 13_960_000, "lagos": 15_388_000}
    found = table.get(city.strip().lower())
    if found is None:
        return {"city": city, "found": False}
    return {"city": city, "population": found, "found": True}


def dispatch(registry: dict[str, Callable], name: str, arguments_json: str) -> Any:
    """Run one tool call and return whatever the tool returns."""
    if name not in registry:
        available = ", ".join(sorted(registry)) or "none"
        raise ToolError(f"unknown tool: {name!r}. Available tools: {available}")
    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, ValueError) as error:
        raise ToolError(f"arguments for {name} were not valid JSON: {error}") from error
    if not isinstance(arguments, dict):
        raise ToolError(f"arguments for {name} must be a JSON object")
    return registry[name](**arguments)


def to_tool_content(result: Any) -> str:
    """Turn a tool's return value into the text that goes back to the model."""
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        # sort_keys so the same result serializes identically every run, which
        # is what makes a prompt cacheable and a transcript diffable.
        return json.dumps(result, sort_keys=True)
    return str(result)


def assistant_turn(choice: Any) -> dict:
    """Record the tool calls the model asked for, before any of them are answered."""
    return {
        "role": "assistant",
        # Often None on a tool call turn. Keep it rather than substituting "":
        # this dict is a record of what the model actually sent.
        "content": choice.message.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    # The raw JSON string, not a re-serialization of it.
                    "arguments": call.function.arguments,
                },
            }
            for call in choice.message.tool_calls or []
        ],
    }


def tool_result_turn(call_id: str, content: str) -> dict:
    """Carry one tool's result back, tagged with the id of the call it answers."""
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def run_agent(
    client,
    registry: dict[str, Callable],
    tools: list[dict],
    question: str,
    max_steps: int = 6,
) -> str:
    """Run the loop until the model produces a final answer."""
    if max_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")

    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(max_steps):
        # The whole conversation, every time. The API holds no state, so the
        # cost of step ten includes everything steps one to nine produced.
        response = client.chat.completions.create(
            model="mock", messages=messages, tools=tools
        )
        choice = response.choices[0]

        if choice.finish_reason == "length":
            raise TruncatedAnswer(
                "the model hit its output limit mid reply; the text is a fragment, "
                "not an answer"
            )

        # The exit condition is the finish_reason and nothing else. Anything
        # that is not a request for tools is the model's final turn.
        if choice.finish_reason != "tool_calls":
            return choice.message.content or ""

        # This must land before any tool message. A tool message that answers
        # no assistant request is a malformed conversation and providers reject
        # it outright.
        messages.append(assistant_turn(choice))

        for call in choice.message.tool_calls:
            result = dispatch(registry, call.function.name, call.function.arguments)
            messages.append(tool_result_turn(call.id, to_tool_content(result)))

    # Raise, do not return a best effort answer. A caller that gets a string
    # back cannot tell a finished run from an abandoned one, and the difference
    # is the whole reason to have a budget.
    raise MaxStepsExceeded(max_steps, messages)
