"""Quarantine, not deletion: a worked solution."""

from __future__ import annotations

import copy


def quarantine_record(result: dict, raw: dict, source: str, received_at: str) -> dict:
    return {
        "row_number": result["row"],
        "source": source,
        "received_at": received_at,
        # Copies, so a later mutation in the pipeline cannot rewrite history.
        "errors": copy.deepcopy(result["errors"]),
        "raw": dict(raw),
    }


def summarise_quarantine(records: list[dict]) -> dict:
    by_field: dict[str, int] = {}
    by_problem: dict[str, int] = {}
    sources: set[str] = set()

    for record in records:
        sources.add(record["source"])
        # Errors, not rows: this summary is for deciding what to fix.
        for error in record["errors"]:
            field = error["field"]
            problem = error["problem"]
            by_field[field] = by_field.get(field, 0) + 1
            by_problem[problem] = by_problem.get(problem, 0) + 1

    return {
        "total": len(records),
        "by_field": by_field,
        "by_problem": by_problem,
        "sources": sorted(sources),
    }


def _rate(day: dict) -> float:
    total = day.get("total", 0)
    if not total:
        return 0.0
    return day.get("broken", 0) / total


def rate_moved(yesterday: dict, today: dict, threshold: float = 2.0) -> dict:
    before = _rate(yesterday)
    after = _rate(today)

    if before == 0:
        # No failures to some failures is exactly the change worth reporting.
        ratio = float("inf") if after > 0 else 0.0
    else:
        ratio = after / before

    return {
        "yesterday_rate": before,
        "today_rate": after,
        "ratio": ratio,
        "moved": ratio >= threshold and after > 0,
    }
