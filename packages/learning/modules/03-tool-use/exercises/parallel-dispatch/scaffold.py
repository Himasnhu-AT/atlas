"""
Parallel tool calls.

One assistant turn can ask for four tools at once. You owe the model four
results, paired by id, before it will speak again, and two of those tools are
going to fail. This is the loop from the last exercise, widened.

Run `python3 test.py` when you think you have it.
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
    """
    What one tool call produced, whether or not it worked.

    Written for you. The important field is `ok`. A failed call still has
    content and still becomes a tool message, because the model is owed an
    answer to every call it made; `ok` is how your own code, your logs and your
    metrics tell the two apart afterwards.
    """

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
    """Serialize a tool's return value for the model. Provided for you."""
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, sort_keys=True)
    return str(result)


def assistant_turn(choice: Any) -> dict:
    """Provided for you: you wrote this in the last exercise."""
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
    """
    Run a single tool call and capture the outcome instead of raising.

    Args:
        call: one entry from choice.message.tool_calls. It has `.id`, and
            `.function.name` and `.function.arguments`, where arguments is a
            JSON string.

    Returns:
        ToolResult(call.id, call.function.name, content, ok).

    Four things can go wrong and all four produce ok=False with a content
    string starting "error: ":
      - the tool name is not in the registry, in which case say so and list
        what is available
      - the arguments are not valid JSON
      - the arguments parse to something that is not an object
      - the tool itself raises

    For the last one, put the exception type and its message in the content:
    "error: LookupError: no population on file for 'Atlantis'". The type alone
    is not enough for the model to act on and the message alone loses the
    distinction between a missing record and a broken database.

    Nothing here raises. That is the whole contract: a function that can raise
    is a function that can leave a batch half answered.
    """
    raise NotImplementedError


def dispatch_all(
    registry: dict[str, Callable],
    calls: list[Any],
    max_workers: int = 4,
) -> list[ToolResult]:
    """
    Run every call in one turn, concurrently, and return the results IN REQUEST
    ORDER.

    The model asked for these together because they do not depend on each
    other, so running them one after another spends the sum of their latencies
    for no reason. Use a ThreadPoolExecutor: tool calls are almost always IO,
    an HTTP request or a query, and threads are the right tool for waiting.

    Completion order is whatever the network decides. Request order is what you
    return. Collect the futures in the order you submitted them and read them
    back in that order, or index the results by position; do not append as
    each one finishes, because that reorders the batch by latency and makes
    every test you write flaky.

    An empty `calls` returns an empty list without starting a pool.

    Returns:
        One ToolResult per call, in the order the calls arrived.
    """
    raise NotImplementedError


def format_tool_messages(calls: list[Any], results: list[ToolResult]) -> list[dict]:
    """
    Pair results back to calls and produce the tool messages.

    Args:
        calls: the calls the model made, in the order it made them.
        results: the results, in any order.

    Returns:
        One {"role": "tool", "tool_call_id": ..., "content": ...} per call, in
        call order.

    Raises:
        ValueError: a call has no result, or a result answers a call that was
            never made. Both are the same underlying bug and both produce a
            conversation the provider rejects, so they fail here, next to the
            code that caused them, rather than as a 400 three functions away.

    Pair on the id, never on position. It is tempting to zip the two lists,
    and it works right up to the first refactor that sorts one of them.
    """
    raise NotImplementedError


def run_agent(
    client,
    registry: dict[str, Callable],
    tools: list[dict],
    question: str,
    max_steps: int = 6,
    max_workers: int = 4,
) -> str:
    """
    Run the loop, handling turns that request several tools at once.

    Flow, per step:
      1. call the model with the whole conversation and the tool list
      2. if finish_reason is not "tool_calls", return the content, or "" if it
         is None
      3. append assistant_turn(choice), once, carrying every call
      4. results = dispatch_all(registry, choice.message.tool_calls, max_workers)
      5. extend the conversation with format_tool_messages(calls, results)

    Raises:
        ValueError: max_steps < 1 or max_workers < 1.
        MaxStepsExceeded: the budget ran out with no answer.

    One assistant message, then N tool messages. Not N assistant messages, and
    not one tool message carrying a summary of all N: the format is fixed and
    the provider counts.
    """
    raise NotImplementedError
