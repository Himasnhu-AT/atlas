"""
Conversation memory.

A conversation that runs long enough will not fit, and something has to go. This
is the layer that decides what: a window that trims from the front, a summary
that trades detail for room, extracted facts worth keeping past the session, and
a manager that composes the three and tells you what it threw away.

The invariant that makes it hard is that message lists are not a flat sequence of
independent items. An assistant message asking for a tool and the tool result
that answers it are one thing, and cutting between them produces a request the
provider rejects.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

#: Prefix on the summary message, so a later pass can recognise its own work.
SUMMARY_PREFIX = "Summary of earlier conversation:"

SUMMARY_INSTRUCTION = (
    "Summarise the conversation below in a few sentences. Keep decisions, "
    "commitments, names and numbers. Drop pleasantries. Write it as notes for "
    "an assistant that will continue the conversation."
)

FACTS_INSTRUCTION = (
    "Read the conversation below and list the durable facts about the user or "
    "their situation, the ones still worth knowing in a week. Reply with a JSON "
    "array of short strings and nothing else. Reply with [] if there are none."
)


def estimate_tokens(message: dict) -> int:
    """
    Given. A rough token count for one message.

    Four characters to a token plus a fixed overhead for the role and framing.
    Real tokenizers disagree with this by ten or twenty percent, which is why the
    budget you pass in should have headroom rather than being the model's exact
    limit. Swap in a real tokenizer and nothing above it changes.
    """
    content = message.get("content") or ""
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        content += (function.get("name") or "") + (function.get("arguments") or "")
    return 4 + len(content) // 4


def render_transcript(messages: list[dict]) -> str:
    """Given. A plain text rendering of a message list, for summarising."""
    lines = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content") or ""
        calls = message.get("tool_calls") or []
        if calls:
            names = ", ".join((call.get("function") or {}).get("name", "?") for call in calls)
            content = f"{content} [called {names}]".strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def tool_groups(messages: list[dict]) -> list[list[dict]]:
    """
    Split a message list into the units that must not be cut apart.

    An assistant message with a non-empty `tool_calls` belongs with every `tool`
    message that immediately follows it: that pair is one exchange, and half of
    it is not a valid request. Every other message is a group of one.

    A `tool` message that follows nothing gets its own group. It is already
    broken and dropping it is fine, but crashing on it is not: this function runs
    on whatever history it is handed, including history some earlier trim
    mangled.

    Returns:
        Groups in the original order, containing the original message objects
        rather than copies. Flattening the result gives you `messages` back.
    """
    raise NotImplementedError


def window(messages: list[dict], max_tokens: int, estimate_fn=estimate_tokens) -> list[dict]:
    """
    Keep the system message and as much recent history as fits.

    Rules:
      1. The LEADING RUN of system messages is always kept, whatever the budget,
         and its cost comes off the budget rather than competing for it. A run
         rather than one message, so that a summary inserted right after the
         original system message is protected too. A system message that turns
         up later in the conversation is history, not instruction, and is
         trimmed like anything else.
      2. Work backwards from the newest group. Add a group while its cost fits
         in the remaining budget, and stop at the first group that does not.
      3. Stop rather than skip. Skipping an oversized group and carrying on to
         older ones leaves a hole in the middle of the conversation, and a model
         reading it will answer the question either side of the gap.
      4. Never split a group, which is what makes rule 2 operate on groups
         rather than messages.

    Args:
        messages: the conversation, oldest first.
        max_tokens: the budget, counting the system message.
        estimate_fn: called with one message, returns its cost.

    Returns:
        A new list, oldest first, that is the system message followed by a
        contiguous run of the most recent groups. Never mutates the input, and
        the messages in the result are the same objects, not copies.
    """
    raise NotImplementedError


def summarize_older(client, messages: list[dict], keep_recent: int = 3) -> list[dict]:
    """
    Replace everything older than the last `keep_recent` groups with a summary.

    Counted in groups, not messages, for the same reason window is: a tool
    exchange is one turn of the conversation however many messages it takes.

    With `keep_recent` or fewer groups there is nothing old enough to summarise.
    Return the messages unchanged and do not call the model. A summarisation
    step that fires on a four message conversation costs a call, adds latency,
    and loses detail to save nothing.

    Otherwise send exactly one chat call:

        [{"role": "system", "content": SUMMARY_INSTRUCTION},
         {"role": "user", "content": render_transcript(<the older messages>)}]

    and return:

        [<the system message, if there was one>,
         {"role": "system", "content": SUMMARY_PREFIX + "\\n" + <the reply>},
         <the messages in the kept groups>]

    The summary goes in as a system message immediately after the original one,
    which puts it inside the run `window` refuses to trim. Insert it anywhere
    else and the next window pass throws away the summary before it throws away
    the turns the summary replaced.

    Providers that mirror the OpenAI chat shape accept more than one system
    message; where a provider does not, the same content goes in the first user
    message instead, and nothing else about this function changes.

    The cost is not the call. It is that a summary is lossy in a way you cannot
    predict: the detail the next question needed is exactly the one the model
    decided was a pleasantry.
    """
    raise NotImplementedError


def extract_facts(client, messages: list[dict]) -> list[str]:
    """
    Ask the model for the durable facts in a conversation.

    One chat call:

        [{"role": "system", "content": FACTS_INSTRUCTION},
         {"role": "user", "content": render_transcript(messages)}]

    The reply is meant to be a JSON array of strings. Parse it with json.loads
    and return the strings, stripped, with empties removed and duplicates
    dropped while keeping the first occurrence.

    Anything else, and that includes valid JSON that is not a list of strings,
    returns []. This is the one place in the module where swallowing an error is
    right: fact extraction is a background nicety, and a model that decided to
    reply with an apology must not take down the turn the user is waiting on.
    Log it, return nothing, carry on.

    An empty message list returns [] without calling the model.
    """
    raise NotImplementedError


@dataclass(frozen=True)
class ManagedContext:
    """
    Given. The result of managing a conversation: what to send, and what it cost.

    Attributes:
        messages: the conversation to send now.
        dropped: the input messages that are not in `messages`, oldest first.
            The summary covers most of what is in here, and `facts` is what was
            worth keeping past the session.
        facts: durable facts extracted from the dropped messages.

    `dropped` exists because a trim is not free and pretending otherwise is how
    you end up debugging an agent that has forgotten something without knowing
    that it forgot anything. Something has to be able to say what went.
    """

    messages: list[dict]
    dropped: list[dict]
    facts: list[str]


def manage(
    client,
    messages: list[dict],
    max_tokens: int,
    keep_recent: int = 3,
    estimate_fn=estimate_tokens,
) -> ManagedContext:
    """
    Fit a conversation into a budget and report what that cost.

    Flow:
      1. If the whole conversation already fits in max_tokens, return it
         unchanged, with no dropped messages, no facts, and no model calls. Most
         turns take this path and it has to be free.
      2. Otherwise summarize_older, then window the result. Summarising first
         means the window is trimming a list that already has the old detail
         compressed into it.
      3. Work out which of the ORIGINAL messages are not in the result. Compare
         by identity, because two turns of a conversation can be equal dicts and
         are not the same message.
      4. If anything was dropped, extract_facts from the dropped messages, so
         what survives is a summary for this session and a fact list for the
         next one. If nothing was dropped, skip the call.

    Returns:
        A ManagedContext. Its `messages` includes the summary message, which was
        not in the input, so `dropped` and `messages` do not add up to the input
        and are not meant to.
    """
    raise NotImplementedError
