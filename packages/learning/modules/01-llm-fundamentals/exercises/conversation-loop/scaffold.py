"""
The conversation loop.

The API is stateless, so a conversation is a list you own, grow, and resend in
full on every turn. You write the thing that owns it: what goes in, what gets
cut, and what a stop reason means.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations


class TruncatedReply(Exception):
    """
    The model stopped because it ran out of output budget.

    The fragment is on `.partial` so a caller can log it, show it, or ask for a
    continuation. What it must not do is become part of the history: every later
    turn would then be conditioned on a sentence that stops halfway, and the
    symptom is a model that seems confused about what it just said.
    """

    def __init__(self, partial: str) -> None:
        super().__init__("the model's reply was cut off by the length limit")
        self.partial = partial


def trim_history(messages: list[dict], keep_last: int) -> list[dict]:
    """
    Keep the system message plus roughly the last `keep_last` messages.

    The system message, if present, is always kept and stays first. Assume at
    most one and that it is first in the input. It is the smallest message in
    the conversation and the only one establishing what the assistant is, so
    dropping it looks like the model got worse rather than like the trimming got
    aggressive.

    Then the exception that makes this function interesting. A tool exchange is
    an assistant message carrying `tool_calls` followed by one `tool` message
    per call. Cut between them and you send a `tool` result whose
    `tool_call_id` refers to a call that is no longer in the conversation, which
    providers reject outright.

    So when the window would begin on a `tool` message, move its start backwards
    until it does not. That means this function is allowed to return MORE than
    `keep_last` messages. When honouring the number would split a tool exchange,
    the number loses: a structurally invalid conversation is worse than a
    slightly long one.

    Args:
        messages: the conversation, oldest first.
        keep_last: how many non-system messages to aim to keep, at least 1.

    Returns:
        A new list holding the same message objects, in their original order.

    Raises:
        ValueError: keep_last is less than 1.
    """
    raise NotImplementedError


class Conversation:
    """
    A chat session over a stateless model.

    Attributes:
        client: a mockllm.MockClient.
        total_tokens_used: running sum of usage.total_tokens over every call
            this conversation has made. Starts at 0.
    """

    def __init__(self, client, system: str | None = None, keep_last: int | None = None) -> None:
        """
        Start a conversation.

        Args:
            client: the model client.
            system: standing instructions. When given, it becomes the first
                message, with role "system". When None the history starts empty.
            keep_last: when set, trim_history() runs before every call with this
                value. When None the history grows without limit, which is the
                right default for short sessions and a bill for long ones.

        Raises:
            ValueError: keep_last is not None and is less than 1.
        """
        raise NotImplementedError

    def send(self, message: str) -> str:
        """
        Send a user message and return the assistant's reply.

        In this order:

          1. Append {"role": "user", "content": message} to the history.
          2. When keep_last is set, replace the history with
             trim_history(history, keep_last). Trimming after the append is what
             guarantees the newest question survives its own trim.
          3. Call client.chat.completions.create(model="mock", messages=history).
          4. Add response.usage.total_tokens to self.total_tokens_used.
          5. If finish_reason is "length", raise TruncatedReply with the partial
             text and append NOTHING. The user message stays, the unusable reply
             does not.
          6. Otherwise append {"role": "assistant", "content": reply} and return
             the reply text.

        Step 4 happens before step 5 on purpose. A truncated reply was still
        generated and still billed, and a token counter that only counts
        successes will disagree with your invoice.

        Raises:
            TruncatedReply: the reply was cut off.
        """
        raise NotImplementedError

    def history(self) -> list[dict]:
        """
        The conversation so far, oldest first.

        Return a copy, deep enough that a caller mutating a message in the
        result cannot rewrite the conversation behind your back.
        """
        raise NotImplementedError

    def reset(self) -> None:
        """
        Clear the history back to just the system message, if there was one.

        Leaves total_tokens_used alone. Those tokens were spent and resetting a
        conversation does not refund them.
        """
        raise NotImplementedError
