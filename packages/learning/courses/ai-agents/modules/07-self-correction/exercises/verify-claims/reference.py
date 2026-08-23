"""Chain of verification: a worked solution."""

from __future__ import annotations

import re

JUDGEMENT_WORDS = [
    "significant",
    "impressive",
    "important",
    "best",
    "excellent",
    "poor",
    "clearly",
    "obviously",
]

UNKNOWN_MARKERS = ["unknown", "not sure", "no information", "cannot"]

MIN_CLAIM_LENGTH = 12


def decompose(draft: str) -> list[dict]:
    claims: list[dict] = []

    for sentence in draft.split(". "):
        # One assertion each: a conjunction joins two claims, and one verdict on
        # both would be a single answer to a question that could be half right.
        for part in sentence.split(" and "):
            text = part.strip().rstrip(".").strip()
            if len(text) < MIN_CLAIM_LENGTH:
                continue
            lowered = text.lower()
            checkable = not any(word in lowered for word in JUDGEMENT_WORDS)
            claims.append({"text": text, "checkable": checkable})

    return claims


def question_for(claim: str) -> str:
    return f"What is true about: {claim}?"


def verify(client, question: str) -> str:
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {"role": "system", "content": "Answer the question directly and briefly."},
            # The question, and nothing else. No draft, no other claims, no
            # reasoning: a check is worth what it did not read.
            {"role": "user", "content": question},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def reconcile(claim: str, answer: str) -> str:
    lowered = answer.lower()

    # First: an answer that does not know is not evidence either way, and
    # treating it as a contradiction deletes true claims.
    if any(marker in lowered for marker in UNKNOWN_MARKERS):
        return "unsupported"

    words = [w for w in re.findall(r"[A-Za-z0-9]+", claim) if len(w) > 3]
    if words and all(word.lower() in lowered for word in words):
        return "supported"

    return "contradicted"


def run_verification(client, draft: str) -> dict:
    claims = decompose(draft)
    counts = {"supported": 0, "contradicted": 0, "unsupported": 0, "skipped": 0}
    out: list[dict] = []
    kept: list[str] = []

    for claim in claims:
        if not claim["checkable"]:
            counts["skipped"] += 1
            out.append({**claim, "verdict": "skipped", "answer": ""})
            kept.append(claim["text"])
            continue

        answer = verify(client, question_for(claim["text"]))
        verdict = reconcile(claim["text"], answer)
        counts[verdict] += 1
        out.append({**claim, "verdict": verdict, "answer": answer})

        if verdict == "supported":
            kept.append(claim["text"])
        elif verdict == "unsupported":
            kept.append(f"{claim['text']} [unverified]")

    final = ". ".join(kept) + "." if kept else ""
    return {"claims": out, "final": final, "counts": counts}
