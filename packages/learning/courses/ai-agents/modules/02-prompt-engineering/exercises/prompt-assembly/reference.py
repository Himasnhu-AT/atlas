"""
Prompt assembly: worked solution.

Selection by word overlap, a per label cap, and the ordering rule that puts the
strongest example nearest the real question.
"""

from __future__ import annotations

import re

#: Words, digits and internal apostrophes. Compiled once at import rather than
#: per call, because select_examples tokenizes the whole bank on every request.
_WORD = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> set[str]:
    """
    Lowercase word set. Duplicates collapse, punctuation separates.

    Words, not the model's tokens. This only compares one string to another, so
    it never has to agree with the model's vocabulary.
    """
    return set(_WORD.findall(text.lower()))


def similarity(a: str, b: str) -> float:
    """Jaccard similarity, and 0.0 when either side has no words."""
    left, right = tokenize(a), tokenize(b)
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union)


def select_examples(
    examples: list[tuple[str, str]],
    user_input: str,
    *,
    k: int = 3,
    max_per_label: int | None = None,
) -> list[tuple[str, str]]:
    """Nearest k examples, capped per label, strongest last."""
    if not examples or k <= 0:
        return []

    # Score with the original index carried along. The index is the tie break,
    # and it is also what keeps the sort stable in the way the docstring
    # promises rather than in the way this particular Python happens to sort.
    scored = [
        (similarity(example_input, user_input), index, example_input, example_output)
        for index, (example_input, example_output) in enumerate(examples)
    ]

    # Score descending, index ascending. Negating the score gives both
    # directions in one key; sorted(reverse=True) would reverse the index too
    # and make ties resolve backwards.
    scored.sort(key=lambda row: (-row[0], row[1]))

    chosen: list[tuple[str, str]] = []
    used: dict[str, int] = {}
    for _score, _index, example_input, example_output in scored:
        if max_per_label is not None and used.get(example_output, 0) >= max_per_label:
            continue
        chosen.append((example_input, example_output))
        used[example_output] = used.get(example_output, 0) + 1
        if len(chosen) == k:
            break

    # Chosen is strongest first, which is the order to select in and the wrong
    # order to send in. Reverse once, at the end.
    chosen.reverse()
    return chosen


def build_messages(
    system: str | None,
    examples: list[tuple[str, str]],
    user_input: str,
) -> list[dict]:
    """System, then the examples as real turns, then the input alone."""
    messages: list[dict] = []
    if system:  # None and "" both mean no system message
        messages.append({"role": "system", "content": system})

    for example_input, example_output in examples:
        messages.append({"role": "user", "content": example_input})
        messages.append({"role": "assistant", "content": example_output})

    messages.append({"role": "user", "content": user_input})
    return messages


def assemble(
    system: str | None,
    bank: list[tuple[str, str]],
    user_input: str,
    *,
    k: int = 3,
    max_per_label: int | None = None,
) -> list[dict]:
    """Select, then assemble."""
    chosen = select_examples(bank, user_input, k=k, max_per_label=max_per_label)
    return build_messages(system, chosen, user_input)
