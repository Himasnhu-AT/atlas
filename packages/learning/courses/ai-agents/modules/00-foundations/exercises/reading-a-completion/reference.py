"""
Reading a completion: worked solution.

Accessors over the object a provider hands back, written so that every decision
is made on finish_reason rather than on the shape of the text.
"""

from __future__ import annotations


class IncompleteReply(Exception):
    """Not a finished answer. Carries the finish_reason that caused it."""

    def __init__(self, finish_reason: str) -> None:
        super().__init__(f"the model stopped for {finish_reason!r}, not 'stop'")
        self.finish_reason = finish_reason


def finish_reason(completion) -> str:
    """The finish_reason of the first choice."""
    return completion.choices[0].finish_reason


def stopped_early(completion) -> bool:
    """True when the reply hit the output cap."""
    # Written against finish_reason() rather than reaching into choices again,
    # so there is one place that knows which choice this code reads.
    return finish_reason(completion) == "length"


def answer_text(completion) -> str:
    """The assistant's text, only when finish_reason is "stop"."""
    reason = finish_reason(completion)
    if reason != "stop":
        # Note the shape of the guard: not "if length" and not "if tool_calls",
        # but "if not stop". A finish reason invented after this was written is
        # then refused rather than silently treated as an answer.
        raise IncompleteReply(reason)
    # A stop turn normally carries text. The `or ""` is there so a provider that
    # returns None on an empty completion hands the caller a string rather than
    # a None that fails three functions later with no clue where it came from.
    return completion.choices[0].message.content or ""


def tool_names(completion) -> list[str]:
    """The requested tool names, in call order."""
    calls = completion.choices[0].message.tool_calls
    # tool_calls is None on a text turn, so this cannot be a bare for loop.
    # `or []` is the whole fix and it is why this function exists.
    return [call.function.name for call in calls or []]


def total_tokens(completion) -> int:
    """Prompt plus completion for one call."""
    usage = completion.usage
    return usage.prompt_tokens + usage.completion_tokens


def usage_totals(completions: list) -> dict[str, int]:
    """Usage summed across every call in a conversation."""
    prompt = sum(c.usage.prompt_tokens for c in completions)
    completion = sum(c.usage.completion_tokens for c in completions)
    # total is derived rather than summed independently, so the three numbers
    # cannot disagree with each other in a report someone is reading.
    return {"prompt": prompt, "completion": completion, "total": prompt + completion}


def describe(completion) -> str:
    """One log line, chosen by finish_reason."""
    reason = finish_reason(completion)
    tokens = total_tokens(completion)

    if reason == "stop":
        return f'stop: "{answer_text(completion)}" ({tokens} tokens)'
    if reason == "length":
        return f"length: truncated after {tokens} tokens"
    if reason == "tool_calls":
        return f"tool_calls: {', '.join(tool_names(completion))} ({tokens} tokens)"
    # The default arm names the value it did not recognise. A log line saying
    # "content_filter" sends you to the provider's changelog in a minute; one
    # that quietly took the "stop" branch sends you nowhere for an afternoon.
    return f"{reason}: unrecognised finish reason ({tokens} tokens)"
