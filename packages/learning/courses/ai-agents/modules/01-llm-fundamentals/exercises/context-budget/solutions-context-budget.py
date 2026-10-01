"""
Context budget: worked solution.

Counting what a conversation costs, what is left, what a loop spends, and what
to throw away when it no longer fits.
"""

from __future__ import annotations

#: Per-message overhead for the role and separators. Approximate by design.
ROLE_OVERHEAD = 3


def estimate_tokens(text: str) -> int:
    """Words times 1.3, floored at 1 for anything non-empty."""
    words = text.split()
    if not words:
        return 0
    return max(1, round(len(words) * 1.3))


def message_tokens(message: dict) -> int:
    """Content plus overhead. Missing content still pays the overhead."""
    # `or ""` rather than a default of "", because the value is frequently an
    # explicit None: that is what an assistant message carrying only tool calls
    # looks like.
    content = message.get("content") or ""
    return estimate_tokens(content) + ROLE_OVERHEAD


def conversation_tokens(messages: list[dict]) -> int:
    """The whole conversation, which is what every turn resends."""
    return sum(message_tokens(message) for message in messages)


def headroom(messages: list[dict], context_window: int, reply_reserve: int) -> int:
    """What is left of the window once the reply's share is set aside."""
    if context_window <= 0:
        raise ValueError(f"context_window must be positive, got {context_window}")
    if reply_reserve < 0:
        raise ValueError(f"reply_reserve must not be negative, got {reply_reserve}")
    if reply_reserve >= context_window:
        raise ValueError(
            f"reply_reserve of {reply_reserve} leaves no room in a window of "
            f"{context_window}"
        )

    # Deliberately not clamped at zero. The size of the overrun is what tells a
    # caller whether to trim one message or summarise the last hour.
    return context_window - reply_reserve - conversation_tokens(messages)


def loop_cost(base_tokens: int, tokens_per_step: int, steps: int) -> int:
    """Prompt tokens across a loop that resends everything on every call."""
    if base_tokens < 0 or tokens_per_step < 0 or steps < 0:
        raise ValueError("loop_cost takes non-negative token counts and step counts")

    # steps * (steps - 1) is always even, so the integer division is exact and
    # the result stays an int rather than drifting into float.
    growth = tokens_per_step * steps * (steps - 1) // 2
    return steps * base_tokens + growth


def trim_to_budget(messages: list[dict], max_tokens: int) -> list[dict]:
    """Pin the system message and the question, then fill backwards."""
    if not messages:
        return []

    system = messages[0] if messages[0].get("role") == "system" else None
    rest = messages[1:] if system is not None else list(messages)

    # The newest user message is non-negotiable: it is the thing being answered.
    last_user_index = None
    for index in range(len(rest) - 1, -1, -1):
        if rest[index].get("role") == "user":
            last_user_index = index
            break

    used = message_tokens(system) if system is not None else 0
    pinned: set[int] = set()
    if last_user_index is not None:
        pinned.add(last_user_index)
        used += message_tokens(rest[last_user_index])

    # Walk backwards, newest first, and stop at the first message that will not
    # fit. Continuing past it would reorder the conversation around a hole, and
    # a hole is invisible to the model reading the result.
    kept = set(pinned)
    for index in range(len(rest) - 1, -1, -1):
        if index in pinned:
            continue
        cost = message_tokens(rest[index])
        if used + cost > max_tokens:
            break
        used += cost
        kept.add(index)

    trimmed = [rest[index] for index in sorted(kept)]
    if system is not None:
        trimmed.insert(0, system)
    return trimmed
