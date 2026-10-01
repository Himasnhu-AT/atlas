"""Self-consistency: a worked solution."""

from __future__ import annotations

import re

PUNCTUATION = ".,!?;:\"'`"

# Words that carry a number without adding meaning to it. "the answer is 42" and
# "42" are the same answer; "42 units were recalled" is not.
CARRIER_WORDS = {
    "answer",
    "approximately",
    "about",
    "roughly",
    "around",
    "that",
    "this",
    "there",
    "value",
    "result",
    "total",
}


def normalise(answer: str) -> str:
    text = answer.strip().lower().strip(PUNCTUATION).strip()
    text = re.sub(r"\s+", " ", text)

    digits = re.findall(r"\d+", text)
    words = [
        w
        for w in re.findall(r"[a-z]+", text)
        if len(w) > 3 and w not in CARRIER_WORDS
    ]
    # One number and nothing substantial around it: the number is the answer,
    # however it was wrapped.
    if len(digits) == 1 and not words:
        return digits[0]

    return text


def sample(client, question: str, n: int = 5, temperature: float = 0.7) -> list[str]:
    out: list[str] = []
    for _ in range(n):
        response = client.chat.completions.create(
            model="mock",
            messages=[{"role": "user", "content": question}],
            temperature=temperature,
        )
        out.append((response.choices[0].message.content or "").strip())
    return out


def tally(answers: list[str]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for answer in answers:
        key = normalise(answer)
        counts[key] = counts.get(key, 0) + 1

    # Count descending, then alphabetically, so a tie breaks the same way every
    # run: a mode that moves between runs is a strange property for a method
    # whose point is stability.
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))


def agree(answers: list[str], split_threshold: float = 0.8) -> dict:
    distribution = tally(answers)

    if not distribution:
        return {
            "answer": "",
            "agreement": 0.0,
            "distribution": [],
            "confidence": "scatter",
            "escalate": True,
        }

    winner, count = distribution[0]
    agreement = count / len(answers)

    if agreement >= split_threshold:
        confidence = "high"
    elif len(distribution) == len(answers) and len(answers) >= 3:
        confidence = "scatter"
    else:
        confidence = "split"

    return {
        "answer": winner,
        "agreement": agreement,
        "distribution": distribution,
        "confidence": confidence,
        "escalate": confidence != "high",
    }


def suits_self_consistency(answers: list[str], max_words: int = 12) -> bool:
    if not answers:
        return False
    return all(len(answer.split()) <= max_words for answer in answers)
