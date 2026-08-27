"""Reflection and its failure mode: a worked solution."""

from __future__ import annotations


def critique(client, draft: str, criteria: list[str]) -> list[str]:
    bullets = "\n".join(f"- {c}" for c in criteria)
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {
                "role": "system",
                "content": (
                    "List findings against the criteria, one per line. "
                    "Reply NONE if there are none."
                ),
            },
            {"role": "user", "content": f"Criteria:\n{bullets}\n\nDraft:\n{draft}"},
        ],
    )

    raw = (response.choices[0].message.content or "").strip()
    if raw.upper() == "NONE":
        return []

    return [line.strip() for line in raw.split("\n") if line.strip()]


def revise(client, draft: str, findings: list[str]) -> str:
    bullets = "\n".join(f"- {f}" for f in findings)
    response = client.chat.completions.create(
        model="mock",
        messages=[
            {
                "role": "system",
                "content": "Revise the draft to address every finding. Change nothing else.",
            },
            {"role": "user", "content": f"Findings:\n{bullets}\n\nDraft:\n{draft}"},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def reflect(client, draft: str, criteria: list[str], max_passes: int = 3) -> dict:
    current = draft
    history: list[dict] = []
    passes = 0
    stopped = "limit"

    for _ in range(max_passes):
        findings = critique(client, current, criteria)

        if not findings:
            history.append({"draft": current, "findings": [], "revised": current})
            stopped = "clean"
            break

        revised = revise(client, current, findings)
        history.append({"draft": current, "findings": findings, "revised": revised})
        current = revised
        passes += 1

    return {"final": current, "passes": passes, "history": history, "stopped": stopped}


def score(text: str, rubric: dict) -> int:
    lowered = text.lower()
    # At most once per key, however often the substring appears.
    return sum(points for needle, points in rubric.items() if needle.lower() in lowered)


def improvement(history: list[dict], rubric: dict) -> list[dict]:
    out: list[dict] = []
    for index, entry in enumerate(history, start=1):
        before = score(entry["draft"], rubric)
        after = score(entry["revised"], rubric)
        if after > before:
            verdict = "better"
        elif after < before:
            verdict = "worse"
        else:
            verdict = "unchanged"
        out.append({"pass": index, "before": before, "after": after, "verdict": verdict})
    return out
