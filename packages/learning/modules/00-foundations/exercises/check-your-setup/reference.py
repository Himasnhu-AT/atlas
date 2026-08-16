"""
Check your setup: worked solution.

Five small functions over a list of chat messages, written the way the rest of
the course writes them.
"""

from __future__ import annotations


def count_words(content: str | None) -> int:
    """Words in one message's content, treating None as empty."""
    # `content or ""` handles both None and "", and it is the idiom you will see
    # in every function in this course that reads a message. Providers really do
    # send content=None, so a bare content.split() is a crash waiting for a tool
    # call to happen.
    return len((content or "").split())


def role_counts(messages: list[dict]) -> dict[str, int]:
    """Message count per role, holding only the roles that appear."""
    counts: dict[str, int] = {}
    for message in messages:
        role = message["role"]
        counts[role] = counts.get(role, 0) + 1
    return counts


def last_user_message(messages: list[dict]) -> str | None:
    """The content of the last message with role "user", or None."""
    # reversed() rather than a slice: it walks backwards without copying the
    # list, and it stops at the first match instead of scanning the whole
    # conversation to keep the one it happens to end on.
    for message in reversed(messages):
        if message["role"] == "user":
            return message.get("content")
    return None


def summarise_messages(messages: list[dict]) -> str:
    """The N messages, M words line, counted across the whole conversation."""
    words = sum(count_words(message.get("content")) for message in messages)
    return f"{len(messages)} messages, {words} words"


def first_reply(client) -> str:
    """One call, one message, the text that comes back."""
    response = client.chat.completions.create(
        model="mock",
        messages=[{"role": "user", "content": "Hello."}],
    )
    # choices is a list because the API can return several candidate replies for
    # one request. Nothing in this course asks for more than one, so index 0
    # every time, and the next lesson explains what the rest of this object is.
    return response.choices[0].message.content
