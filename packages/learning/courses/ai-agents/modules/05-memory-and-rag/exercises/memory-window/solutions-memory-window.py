"""
Conversation memory: reference solution.

Read this after your own attempt. The comments are about the decisions, not the
syntax, because the decisions are the part that transfers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

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
    content = message.get("content") or ""
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        content += (function.get("name") or "") + (function.get("arguments") or "")
    return 4 + len(content) // 4


def render_transcript(messages: list[dict]) -> str:
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
    groups: list[list[dict]] = []
    for message in messages:
        # A tool result joins the group ahead of it only if that group is an
        # assistant message that actually asked for a tool. Checking the
        # previous group rather than a running flag means an orphaned tool
        # message lands in its own group instead of attaching to whatever
        # happened to come before it.
        if message.get("role") == "tool" and groups:
            head = groups[-1][0]
            if head.get("role") == "assistant" and head.get("tool_calls"):
                groups[-1].append(message)
                continue
        groups.append([message])
    return groups


def _system_prefix(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    The leading run of system messages, and everything after it.

    A run rather than a single message, so a summary inserted directly after the
    original system message is protected too. Only the leading run counts: a
    system message that turns up in the middle of a conversation is history, not
    instruction, and it is trimmed like anything else.
    """
    cut = 0
    while cut < len(messages) and messages[cut].get("role") == "system":
        cut += 1
    return list(messages[:cut]), list(messages[cut:])


def window(messages: list[dict], max_tokens: int, estimate_fn=estimate_tokens) -> list[dict]:
    system, rest = _system_prefix(messages)

    # The system message is not negotiable, so it comes off the budget rather
    # than competing for it. A budget smaller than the system message leaves
    # this negative, which correctly means nothing else fits.
    budget = max_tokens - sum(estimate_fn(message) for message in system)

    kept: list[list[dict]] = []
    for group in reversed(tool_groups(rest)):
        cost = sum(estimate_fn(message) for message in group)
        if cost > budget:
            # Stop, do not skip. Carrying on to older groups would produce a
            # conversation with a hole in it, which reads as a coherent history
            # and is not one.
            break
        budget -= cost
        kept.append(group)

    kept.reverse()
    return system + [message for group in kept for message in group]


def summarize_older(client, messages: list[dict], keep_recent: int = 3) -> list[dict]:
    system, rest = _system_prefix(messages)
    groups = tool_groups(rest)

    # Nothing old enough to be worth a call. Returning early here is what keeps
    # short conversations free.
    if len(groups) <= keep_recent:
        return list(messages)

    older = [message for group in groups[: len(groups) - keep_recent] for message in group]
    recent = [message for group in groups[len(groups) - keep_recent :] for message in group]

    response = client.chat.completions.create(
        model="mock",
        messages=[
            {"role": "system", "content": SUMMARY_INSTRUCTION},
            {"role": "user", "content": render_transcript(older)},
        ],
    )
    summary = response.choices[0].message.content or ""

    return [
        *system,
        {"role": "system", "content": f"{SUMMARY_PREFIX}\n{summary}"},
        *recent,
    ]


def extract_facts(client, messages: list[dict]) -> list[str]:
    if not messages:
        return []

    response = client.chat.completions.create(
        model="mock",
        messages=[
            {"role": "system", "content": FACTS_INSTRUCTION},
            {"role": "user", "content": render_transcript(messages)},
        ],
    )

    try:
        parsed = json.loads(response.choices[0].message.content or "")
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(parsed, list):
        return []

    facts: list[str] = []
    for item in parsed:
        # Not a string means the model answered a different question from the
        # one asked. Skipping the item rather than str()ing it keeps a stray
        # {"fact": ...} out of the memory store.
        if not isinstance(item, str):
            continue
        fact = item.strip()
        if fact and fact not in facts:
            facts.append(fact)
    return facts


@dataclass(frozen=True)
class ManagedContext:
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
    if sum(estimate_fn(message) for message in messages) <= max_tokens:
        return ManagedContext(messages=list(messages), dropped=[], facts=[])

    summarised = summarize_older(client, messages, keep_recent=keep_recent)
    trimmed = window(summarised, max_tokens, estimate_fn=estimate_fn)

    # Identity, not equality. {"role": "user", "content": "ok"} appearing twice
    # in a conversation is two messages, and an equality check would report the
    # surviving one as proof that the dropped one is still there.
    surviving = {id(message) for message in trimmed}
    dropped = [message for message in messages if id(message) not in surviving]

    facts = extract_facts(client, dropped) if dropped else []
    return ManagedContext(messages=trimmed, dropped=dropped, facts=facts)
