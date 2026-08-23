"""
When tools fail: worked solution.

Three failures go back to the model as observations, one goes into a retry, and
the run always ends with something the caller can act on.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from mockllm import APIError

RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class AgentRun:
    """Everything the caller needs to know about one run."""

    answer: str
    ok: bool
    reason: str
    steps: int
    messages: list[dict] = field(default_factory=list)


def lookup_population(city: str) -> dict:
    """Look up the population of a city."""
    table = {"paris": 2_102_650, "tokyo": 13_960_000, "lagos": 15_388_000}
    found = table.get(city.strip().lower())
    if found is None:
        raise LookupError(
            f"no population on file for {city!r}. On file: {', '.join(sorted(table))}"
        )
    return {"city": city, "population": found}


def to_tool_content(result: Any) -> str:
    """Serialize a tool's return value for the model."""
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, sort_keys=True)
    return str(result)


def assistant_turn(choice: Any) -> dict:
    """The assistant message recording what the model asked for."""
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


def call_signature(name: str, arguments_json: str) -> str:
    """A stable key for one exact call, so repeats can be counted."""
    try:
        canonical = json.dumps(json.loads(arguments_json), sort_keys=True)
    except (json.JSONDecodeError, ValueError, TypeError):
        # Unparseable arguments are still a repeat when they repeat, and this
        # is the case that loops hardest: the model cannot see why its JSON is
        # rejected, so it sends the same JSON again.
        canonical = arguments_json
    return f"{name}({canonical})"


def safe_dispatch(
    registry: dict[str, Callable], name: str, arguments_json: str
) -> tuple[str, bool]:
    """Run one tool call, turning the recoverable failures into observations."""
    fn = registry.get(name)
    if fn is None:
        available = ", ".join(sorted(registry)) or "none"
        return f"error: unknown tool {name!r}. Available tools: {available}", False

    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, ValueError) as error:
        return f"error: arguments for {name} were not valid JSON: {error}", False

    if not isinstance(arguments, dict):
        return (
            f"error: arguments for {name} must be a JSON object, got "
            f"{type(arguments).__name__}",
            False,
        )

    try:
        result = fn(**arguments)
    except TypeError as error:
        # A TypeError from the call itself is usually a wrong argument list,
        # which is the model's mistake and worth naming as such.
        return f"error: wrong arguments for {name}: {error}", False
    except Exception as error:
        return f"error: {type(error).__name__}: {error}", False

    return to_tool_content(result), True


def call_with_retry(
    client,
    messages: list[dict],
    tools: list[dict],
    attempts: int = 3,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Call the model, retrying a failure of the provider itself."""
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, got {attempts}")

    for attempt in range(attempts):
        try:
            return client.chat.completions.create(
                model="mock", messages=messages, tools=tools
            )
        except APIError as error:
            if error.status_code not in RETRYABLE_STATUS:
                # A 400 or a 401 will fail the same way every time. Retrying it
                # turns one clear error into three and delays the fix.
                raise
            if attempt == attempts - 1:
                raise
            # Doubling, so a provider that is briefly overloaded is not hit at
            # the same rate that overloaded it. Production adds jitter.
            sleep(base_delay * (2**attempt))

    # Unreachable: the loop either returns or raises. Kept so the function has
    # one obvious exit if the loop above is ever edited.
    raise RuntimeError("call_with_retry fell out of its loop")


def run_resilient_agent(
    client,
    registry: dict[str, Callable],
    tools: list[dict],
    question: str,
    max_steps: int = 6,
    attempts: int = 3,
    repeat_limit: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> AgentRun:
    """Run the loop, surviving what can be survived and reporting what cannot."""
    if max_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")
    if attempts < 1:
        raise ValueError(f"attempts must be at least 1, got {attempts}")
    if repeat_limit < 1:
        raise ValueError(f"repeat_limit must be at least 1, got {repeat_limit}")

    messages: list[dict] = [{"role": "user", "content": question}]
    failures: dict[str, int] = {}
    steps = 0

    for _ in range(max_steps):
        steps += 1
        try:
            response = call_with_retry(client, messages, tools, attempts, sleep=sleep)
        except APIError:
            # Not an observation. The model never saw the request, so there is
            # nothing for it to reason about and nothing to append.
            return AgentRun("", False, "provider_error", steps, messages)

        choice = response.choices[0]
        if choice.finish_reason != "tool_calls":
            return AgentRun(choice.message.content or "", True, "answered", steps, messages)

        messages.append(assistant_turn(choice))

        stuck = False
        for call in choice.message.tool_calls:
            content, ok = safe_dispatch(
                registry, call.function.name, call.function.arguments
            )
            # Every call is answered, failed or not, before anything else
            # happens. Bailing out mid batch leaves a malformed conversation
            # behind, which is a worse bug than the one you were bailing on.
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": content}
            )
            if not ok:
                signature = call_signature(call.function.name, call.function.arguments)
                failures[signature] = failures.get(signature, 0) + 1
                if failures[signature] >= repeat_limit:
                    stuck = True

        if stuck:
            return AgentRun("", False, "repeated_failure", steps, messages)

    return AgentRun("", False, "max_steps", steps, messages)
