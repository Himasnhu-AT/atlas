"""
Reading a completion.

Pure functions over the object a provider hands back. No loop, no agent, no
framework. Everything in the rest of the course reaches into this object, and it
is worth writing the accessors once, deliberately, while there is nothing else
going on.

The theme running through all of them: branch on finish_reason, never on what
the text looks like.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


class IncompleteReply(Exception):
    """
    The completion is not a finished answer, so there is no text to hand on.

    Carries the finish_reason that caused it, because the caller's next move
    depends on which one it was. "length" means ask again with more room or a
    shorter prompt. "tool_calls" means run the tools and call the model again.
    Collapsing them into one bare exception throws away the only information
    that would tell the two apart.
    """

    def __init__(self, finish_reason: str) -> None:
        super().__init__(f"the model stopped for {finish_reason!r}, not 'stop'")
        self.finish_reason = finish_reason


def finish_reason(completion) -> str:
    """
    The finish_reason of the first choice.

    Args:
        completion: a mockllm.Completion, shaped like the one an OpenAI
            compatible provider returns.

    Returns:
        The string the provider set: "stop", "length", "tool_calls", or
        something newer that did not exist when this course was written.

    `choices` is a list because the API can return several candidate replies to
    one request. Nothing here asks for more than one, so index 0, but index it
    deliberately rather than assuming the list is a single object.
    """
    raise NotImplementedError


def stopped_early(completion) -> bool:
    """
    Did the model run out of output budget?

    Returns:
        True when finish_reason is "length", False otherwise.

    "length" means the reply hit the output cap mid sentence. The text that came
    back is real text and it reads like an answer, which is exactly why this
    needs checking rather than eyeballing.
    """
    raise NotImplementedError


def answer_text(completion) -> str:
    """
    The assistant's text, but only when the turn actually finished.

    Returns:
        The content of the first choice's message, or "" when the provider
        finished normally and sent no content.

    Raises:
        IncompleteReply: finish_reason is anything other than "stop". Pass the
            finish_reason into the exception so the caller can tell a truncation
            from a tool call.

    The reason this raises instead of returning the half sentence is that a
    truncated reply is indistinguishable from a finished one downstream. Once it
    has been stored in a database or shown to a customer, nothing in the system
    remembers it was cut off.
    """
    raise NotImplementedError


def tool_names(completion) -> list[str]:
    """
    The names of the tools the model asked for, in the order it asked.

    Returns:
        A list of names, or an empty list when this turn requested no tools.

    The invariant that catches people: on a text turn `message.tool_calls` is
    None, not an empty list. Iterating it directly raises TypeError on every
    ordinary reply your agent ever receives.

    Order matters and is worth preserving. A model that asks to read a file and
    then write it is describing a sequence, and running the two in dict order or
    in whatever order a set gives you is a bug that only shows up in production.
    """
    raise NotImplementedError


def total_tokens(completion) -> int:
    """
    Everything this one call cost, prompt plus completion.

    Returns:
        completion.usage.prompt_tokens + completion.usage.completion_tokens.

    prompt_tokens counts the entire conversation you sent, not the newest
    message. That is the number that grows.
    """
    raise NotImplementedError


def usage_totals(completions: list) -> dict[str, int]:
    """
    What a whole conversation cost, across every call in it.

    Args:
        completions: the completions from one conversation, oldest first.

    Returns:
        {"prompt": ..., "completion": ..., "total": ...}, summed across the
        list. An empty list gives all three as 0.

    Sum every turn rather than reading the last one. The last completion's usage
    describes the last call alone, and a five turn conversation is five separate
    charges. Prompt tokens are re-sent and re-billed on every one of them, which
    is why an agent that keeps appending to a message list gets more expensive
    per step even when the model's replies stay short.
    """
    raise NotImplementedError


def describe(completion) -> str:
    """
    One line naming what came back, for a log you will actually read later.

    Composes the functions above. The format is exact, chosen by finish_reason,
    with N being total_tokens(completion):

        finish_reason   the line describe() returns
        -------------   ----------------------------------------------
        stop            stop: "Six on weekdays." (N tokens)
        length          length: truncated after N tokens
        tool_calls      tool_calls: get_hours, get_address (N tokens)
        anything else   content_filter: unrecognised finish reason (N tokens)

    Four details in that table are deliberate and are the ones worth reading
    twice. The length line ends in a bare count with no parentheses, because it
    is a sentence rather than an annotation on an answer. On the last row,
    content_filter is standing in for whatever the actual finish_reason was, so
    that line is built from the value you received; the words after the colon are
    literal. The text of a stop turn is wrapped in double quotes. And tool names
    are joined with a comma and a space, in call order.

    A stop turn that sent no content renders its empty text the same way the rest
    of this exercise treats it, as "" between the quotes.

    That last arm is the point of the exercise. The set of finish reasons is
    open: providers add values, and a branch written as if there were exactly
    three ends up treating a new one as whichever arm happens to be last. Name
    the reason you did not handle instead of guessing.
    """
    raise NotImplementedError
