"""
Context budget.

Every turn resends the whole conversation, so the size of that conversation is
the thing that breaks first and the thing that costs the most. This is the
accounting layer: count what a turn costs, work out what is left, and decide
what to drop when there is not enough room.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

#: Providers add a few tokens per message for the role and the separators. The
#: exact number varies and none of them promise it; 3 is close enough that the
#: overhead does not disappear from your estimate, which is what matters when a
#: conversation is fifty short messages rather than one long one.
ROLE_OVERHEAD = 3


def estimate_tokens(text: str) -> int:
    """
    Approximate the token cost of a string.

    Use this formula exactly, so your numbers match the tests:

        max(1, round(number_of_whitespace_separated_words * 1.3))

    An empty or whitespace-only string costs 0, not 1. The floor of 1 exists so
    that a single word never rounds down to nothing; nothing is the right answer
    only when there was nothing there.

    The 1.3 is the usual English prose ratio and it is an estimate, not a
    tokenizer. Code and non-English text run higher. When a number has to be
    right, count it with the provider's tokenizer.

    Examples:
        >>> estimate_tokens("")
        0
        >>> estimate_tokens("one two three")
        4
    """
    raise NotImplementedError


def message_tokens(message: dict) -> int:
    """
    Cost of one message: its content plus ROLE_OVERHEAD.

    A message whose content is None or absent still costs the overhead, because
    the role and the separators are still sent. An assistant message that only
    carries tool calls is exactly that case, and treating it as free is how a
    tool-heavy conversation quietly overruns a budget you thought you had
    checked.

    Args:
        message: a chat message dict. Only "content" is read.
    """
    raise NotImplementedError


def conversation_tokens(messages: list[dict]) -> int:
    """Total cost of a list of messages. An empty conversation costs 0."""
    raise NotImplementedError


def headroom(messages: list[dict], context_window: int, reply_reserve: int) -> int:
    """
    How many tokens are left for more input.

    The context window is one budget covering the prompt and the reply together,
    so the room available for history is the window minus what you are holding
    back for the model to write into.

    Return a NEGATIVE number when the conversation has already overrun. A
    caller needs to know by how much in order to decide what to do, and clamping
    at zero throws that away.

    Args:
        messages: the conversation so far.
        context_window: the model's total sequence limit.
        reply_reserve: tokens held back for the reply. Reserving nothing is
            legal and gets you a reply that stops mid sentence.

    Returns:
        context_window - reply_reserve - conversation_tokens(messages).

    Raises:
        ValueError: context_window is not positive, reply_reserve is negative,
            or reply_reserve is not smaller than context_window.
    """
    raise NotImplementedError


def loop_cost(base_tokens: int, tokens_per_step: int, steps: int) -> int:
    """
    Total prompt tokens billed across an agent loop.

    The model has no memory, so step 1 sends `base_tokens`, step 2 sends
    `base_tokens + tokens_per_step`, step 3 sends `base_tokens + 2 *
    tokens_per_step`, and so on. Sum that over `steps` calls.

    The closed form is `steps * base_tokens + tokens_per_step * steps *
    (steps - 1) // 2`, and the second term is the point of the exercise: it is
    quadratic in the step count. Doubling the number of steps roughly
    quadruples the resend cost, which is why an agent that fails to terminate
    is a billing incident and not a hang.

    This counts prompt tokens only. Output tokens are the `tokens_per_step`
    growth, billed once each at their own rate.

    Args:
        base_tokens: the prompt before the loop starts.
        tokens_per_step: what each step appends to the conversation.
        steps: how many model calls the loop makes. 0 costs 0.

    Raises:
        ValueError: any argument is negative.
    """
    raise NotImplementedError


def trim_to_budget(messages: list[dict], max_tokens: int) -> list[dict]:
    """
    Drop the oldest messages until the conversation fits max_tokens.

    Rules, in order:

      1. The system message is always kept and stays first. Assume at most one,
         and that it is first in the input if present.
      2. The most recent message with role "user" is always kept. It is the
         question; a conversation that fits the budget and has dropped the
         question is not a saving.
      3. Fill whatever budget remains with the newest other messages, working
         backwards. Stop at the first message that does not fit.
      4. Return the kept messages in their original relative order.
      5. If the two pinned messages alone exceed max_tokens, return just those.
         Going over budget with the question intact is a decision the caller can
         handle; silently answering nothing is not.

    Rule 3 is the one people get wrong. Stopping is deliberate: skipping the
    message that did not fit and continuing to look for a smaller one further
    back leaves a hole in the middle of the conversation. The model reads what
    you send as continuous, so a hole is not a shorter conversation, it is a
    conversation where somebody's reply answers a question that is no longer
    there.

    Args:
        messages: the full conversation, oldest first.
        max_tokens: the budget, measured with message_tokens().

    Returns:
        A NEW list. Do not mutate the input, and do not copy the message dicts
        either: the caller expects the same objects back, just fewer of them.
    """
    raise NotImplementedError
