"""
Parallel tool calls: worked solution.

Run the batch concurrently, keep the batch in request order, and answer every
call including the ones that failed.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable


class MaxStepsExceeded(Exception):
    """The step budget ran out before the model produced a final answer."""

    def __init__(self, steps: int, messages: list[dict]) -> None:
        super().__init__(
            f"the agent used all {steps} model calls without producing an answer"
        )
        self.steps = steps
        self.messages = messages


@dataclass(frozen=True)
class ToolResult:
    """What one tool call produced, whether or not it worked."""

    call_id: str
    name: str
    content: str
    ok: bool


def lookup_population(city: str) -> dict:
    """Look up the population of a city."""
    table = {"paris": 2_102_650, "tokyo": 13_960_000, "lagos": 15_388_000}
    found = table.get(city.strip().lower())
    if found is None:
        raise LookupError(f"no population on file for {city!r}")
    return {"city": city, "population": found}


def lookup_timezone(city: str) -> str:
    """Look up the IANA timezone of a city."""
    table = {"paris": "Europe/Paris", "tokyo": "Asia/Tokyo", "lagos": "Africa/Lagos"}
    found = table.get(city.strip().lower())
    if found is None:
        raise LookupError(f"no timezone on file for {city!r}")
    return found


def to_tool_content(result: Any) -> str:
    """Serialize a tool's return value for the model."""
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, sort_keys=True)
    return str(result)


def assistant_turn(choice: Any) -> dict:
    """One assistant message carrying every call in the turn."""
    return {
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
            for call in choice.message.tool_calls or []
        ],
    }


def run_one(registry: dict[str, Callable], call: Any) -> ToolResult:
    """Run one call, turning every failure into a result rather than a raise."""
    name = call.function.name

    def failed(message: str) -> ToolResult:
        return ToolResult(call.id, name, f"error: {message}", ok=False)

    fn = registry.get(name)
    if fn is None:
        available = ", ".join(sorted(registry)) or "none"
        return failed(f"unknown tool: {name!r}. Available tools: {available}")

    try:
        arguments = json.loads(call.function.arguments)
    except (json.JSONDecodeError, ValueError) as error:
        return failed(f"arguments for {name} were not valid JSON: {error}")

    if not isinstance(arguments, dict):
        return failed(f"arguments for {name} must be a JSON object")

    try:
        result = fn(**arguments)
    except Exception as error:
        # The type as well as the message. "LookupError: no population on file
        # for 'Atlantis'" tells the model to try a different city; "the
        # database is unreachable" tells it to stop trying.
        return failed(f"{type(error).__name__}: {error}")

    return ToolResult(call.id, name, to_tool_content(result), ok=True)


def dispatch_all(
    registry: dict[str, Callable],
    calls: list[Any],
    max_workers: int = 4,
) -> list[ToolResult]:
    """Run a whole turn's calls concurrently, returning results in request order."""
    if not calls:
        # No pool, no threads. A batch of nothing is a common shape once tool
        # choice gets involved and it should cost nothing.
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        # submit in request order, then read the futures back in that same
        # order. as_completed() would hand them over by latency, which is
        # exactly the ordering the message protocol must not inherit.
        futures = [pool.submit(run_one, registry, call) for call in calls]
        return [future.result() for future in futures]


def format_tool_messages(calls: list[Any], results: list[ToolResult]) -> list[dict]:
    """Pair results back to calls by id and emit the tool messages in call order."""
    by_id = {result.call_id: result for result in results}
    requested = [call.id for call in calls]

    missing = [call_id for call_id in requested if call_id not in by_id]
    if missing:
        raise ValueError(
            f"no result for tool call(s) {', '.join(missing)}. Every call in a turn "
            f"must be answered before the next model call, or the conversation is "
            f"malformed."
        )

    extra = sorted(set(by_id) - set(requested))
    if extra:
        raise ValueError(
            f"result(s) for tool call(s) that were never made: {', '.join(extra)}"
        )

    # Call order, not result order. Pairing is by id; ordering is by request.
    return [
        {"role": "tool", "tool_call_id": call.id, "content": by_id[call.id].content}
        for call in calls
    ]


def run_agent(
    client,
    registry: dict[str, Callable],
    tools: list[dict],
    question: str,
    max_steps: int = 6,
    max_workers: int = 4,
) -> str:
    """Run the loop, handling turns that request several tools at once."""
    if max_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")
    if max_workers < 1:
        raise ValueError(f"max_workers must be at least 1, got {max_workers}")

    messages: list[dict] = [{"role": "user", "content": question}]

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model="mock", messages=messages, tools=tools
        )
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            return choice.message.content or ""

        calls = list(choice.message.tool_calls or [])
        # One assistant message for the whole turn, however many calls it made.
        messages.append(assistant_turn(choice))

        results = dispatch_all(registry, calls, max_workers)
        messages.extend(format_tool_messages(calls, results))

    raise MaxStepsExceeded(max_steps, messages)
