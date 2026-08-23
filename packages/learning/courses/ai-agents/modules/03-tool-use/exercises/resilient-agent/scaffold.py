"""
When tools fail.

Four things go wrong in an agent run and only three of them are the model's
problem. Sorting them out is the difference between a loop that survives a bad
afternoon and one that crashes on the first typo.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from mockllm import APIError

# Status codes worth trying again. A 429 means slow down and a 5xx means the
# other end is having a moment; both are likely to be different in a second.
# Everything else, and a 400 above all, will fail identically forever, so
# retrying it spends your budget to learn nothing.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class AgentRun:
    """
    Everything the caller needs to know about one run.

    Written for you. Note that this is a return value and not an exception,
    which is a deliberate change from the loop you wrote earlier. Inside the
    loop, running out of budget is a bug and raising is right. At the boundary
    where an agent meets the rest of your program, "I could not finish" is an
    ordinary outcome that a queue worker or an HTTP handler has to render, and
    an outcome you have to render is data.

    Attributes:
        answer: the model's final text, or "" if it never got there.
        ok: whether the run produced an answer.
        reason: "answered", "max_steps", "repeated_failure" or "provider_error".
        steps: model calls actually made.
        messages: the whole transcript, for logs and for the next engineer.
    """

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
    """Serialize a tool's return value for the model. Provided for you."""
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, sort_keys=True)
    return str(result)


def assistant_turn(choice: Any) -> dict:
    """Provided for you: you wrote this two exercises ago."""
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
    """
    A stable key for "this exact call", so repeats can be counted.

    Two calls with the same arguments in a different key order are the same
    call. Parse the JSON and re-serialize it with sorted keys rather than
    comparing the raw strings, or a model that emits {"a":1,"b":2} and then
    {"b":2,"a":1} looks like it is making progress.

    Returns:
        f"{name}({canonical_json})". When the arguments do not parse, fall back
        to f"{name}({arguments_json})", because a model repeating the same
        malformed call is exactly the loop this function exists to catch.
    """
    raise NotImplementedError


def safe_dispatch(
    registry: dict[str, Callable], name: str, arguments_json: str
) -> tuple[str, bool]:
    """
    Run one tool call, turning the three recoverable failures into observations.

    Returns:
        (content, ok). On success, (to_tool_content(result), True). On any of
        the recoverable failures, (f"error: ...", False).

    The three recoverable failures are the ones the model can do something
    about, and each needs a different sentence back. The tests read these
    strings, so what they contain is part of the specification even though the
    wording is yours:
      - the tool does not exist: name the tool that was asked for, and list the
        tools that do exist
      - the arguments are not valid JSON, or not an object: name the tool and
        say what was received
      - the tool raised: give the exception type and its message verbatim,
        including any hint the tool put there. A TypeError from calling the
        function is this case too, so a wrong argument name ends up named in
        the observation.

    A good error observation names what failed, why, and what would work
    instead. "error: unknown tool 'lookup_pop'. Available tools:
    lookup_population" gets the next call right. "error: KeyError" gets you the
    same wrong call three more times.

    Nothing here raises.
    """
    raise NotImplementedError


def call_with_retry(
    client,
    messages: list[dict],
    tools: list[dict],
    attempts: int = 3,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """
    Call the model, retrying a failure of the provider itself.

    This is the fourth failure and the one that does not belong in the
    conversation. A 503 is not an observation the model can reason about; it is
    the same request needing to be sent again. Feeding it back as a tool result
    teaches the model that its perfectly good call was wrong.

    Args:
        attempts: total tries, not extra tries. attempts=1 means no retry.
        base_delay: the first wait. Double it each time, so the waits for
            attempts=3 are base_delay and then base_delay * 2.
        sleep: injected so tests do not actually wait. Production code adds
            jitter here, a small random offset, so that a thousand clients
            failing at once do not all come back at the same instant. This one
            is deterministic on purpose.

    Returns:
        The completion, on the first attempt that succeeds.

    Raises:
        ValueError: attempts < 1.
        APIError: the last one, when the attempts are gone. Re-raise the
            provider's error rather than inventing your own, because its status
            code is what the caller upstream will want.

    Only retry a status code in RETRYABLE_STATUS. Anything else is re-raised
    immediately: a 401 does not get better on the second try, and a 400 means
    the request you built is wrong, which retrying hides.
    """
    raise NotImplementedError


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
    """
    Run the loop so that it survives what can be survived and reports what cannot.

    Flow, per step:
      1. call_with_retry(client, messages, tools, attempts, sleep=sleep). If it
         raises APIError, the run is over: return AgentRun("", False,
         "provider_error", steps, messages).
      2. finish_reason that is not "tool_calls" ends the run:
         AgentRun(content or "", True, "answered", steps, messages).
      3. append assistant_turn(choice).
      4. for each call, in order: safe_dispatch it and append
         {"role": "tool", "tool_call_id": call.id, "content": content}. Every
         call gets its message, failed or not.
      5. count the failures. Keep a count per call_signature, incremented only
         when a call FAILED. When any signature's count reaches repeat_limit,
         finish the step's tool messages and then return AgentRun("", False,
         "repeated_failure", steps, messages).

    A spent budget returns AgentRun("", False, "max_steps", steps, messages).

    Args:
        repeat_limit: how many times one identical call may fail before the run
            gives up on it. This is the guard that stops the most expensive
            failure in agent work: a model that responds to an error by making
            the same call again, forever, at full price. max_steps alone caps
            the bill but not the wasted latency, and it cannot tell a run that
            was working from one that was stuck.

    Raises:
        ValueError: max_steps, attempts or repeat_limit below 1.

    `steps` is the number of model calls actually made, including the one that
    failed. Retries inside one step are not steps.
    """
    raise NotImplementedError
