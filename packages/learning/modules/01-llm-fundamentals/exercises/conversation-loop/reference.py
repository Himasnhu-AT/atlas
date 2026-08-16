"""
The conversation loop: worked solution.

Turning a stateless endpoint into something that remembers, by keeping the list
yourself and being deliberate about what leaves it.
"""

from __future__ import annotations


class TruncatedReply(Exception):
    """The model stopped on the length limit. The fragment is on `.partial`."""

    def __init__(self, partial: str) -> None:
        super().__init__("the model's reply was cut off by the length limit")
        self.partial = partial


def trim_history(messages: list[dict], keep_last: int) -> list[dict]:
    """A sliding window over exchanges rather than over messages."""
    if keep_last < 1:
        raise ValueError(f"keep_last must be at least 1, got {keep_last}")

    if not messages:
        return []

    system = messages[0] if messages[0].get("role") == "system" else None
    rest = messages[1:] if system is not None else list(messages)

    start = max(0, len(rest) - keep_last)

    # Walk the boundary backwards off any orphaned tool results. Each step back
    # passes one `tool` message, and the message before the run of them is the
    # assistant turn that requested the calls, so the loop lands exactly on it.
    # This can keep more than keep_last messages. That is the point: a `tool`
    # message whose matching call is missing is rejected by the provider, and a
    # window that is one message too long is not.
    while start > 0 and rest[start].get("role") == "tool":
        start -= 1

    kept = rest[start:]
    return [system, *kept] if system is not None else list(kept)


class Conversation:
    """A chat session over a stateless model."""

    def __init__(self, client, system: str | None = None, keep_last: int | None = None) -> None:
        if keep_last is not None and keep_last < 1:
            raise ValueError(f"keep_last must be at least 1 or None, got {keep_last}")

        self.client = client
        self.total_tokens_used = 0
        self.keep_last = keep_last
        self._system = system
        self._messages: list[dict] = []
        if system is not None:
            self._messages.append({"role": "system", "content": system})

    def send(self, message: str) -> str:
        self._messages.append({"role": "user", "content": message})

        # Trim after appending, never before. Trimming first and then adding the
        # question can push the window one over; trimming last means the newest
        # question is always inside it.
        if self.keep_last is not None:
            self._messages = trim_history(self._messages, self.keep_last)

        response = self.client.chat.completions.create(
            model="mock",
            messages=self._messages,
        )

        # Counted before the branch below, because a truncated reply was
        # generated and billed like any other.
        self.total_tokens_used += response.usage.total_tokens

        choice = response.choices[0]
        reply = choice.message.content or ""

        if choice.finish_reason == "length":
            raise TruncatedReply(reply)

        self._messages.append({"role": "assistant", "content": reply})
        return reply

    def history(self) -> list[dict]:
        # A new outer list of new dicts. Returning the inner dicts by reference
        # would let a caller edit the conversation by editing what looks like a
        # read-only snapshot.
        return [dict(message) for message in self._messages]

    def reset(self) -> None:
        self._messages = []
        if self._system is not None:
            self._messages.append({"role": "system", "content": self._system})
