"""
An orchestrator and its workers: worked solution.

The fan out is a loop. The work is in refusing a plan that cannot be fanned out,
keeping each worker's context to its own subtask, and settling contradictions
without inventing a winner.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mockllm import APIError


@dataclass(frozen=True)
class Subtask:
    """One unit of work, answerable without any other subtask's output."""

    id: str
    goal: str
    key: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerResult:
    """What one worker returns: a checkable claim, not a paragraph."""

    subtask_id: str
    status: str
    key: str = ""
    value: str = ""
    confidence: float = 0.0
    evidence: str = ""
    note: str = ""


@dataclass(frozen=True)
class Conflict:
    """Two or more workers answered the same key differently."""

    key: str
    claims: tuple[tuple[str, str, float], ...]
    winner: str | None


@dataclass(frozen=True)
class Aggregate:
    """What the run actually established, and what it did not."""

    findings: dict[str, str]
    conflicts: tuple[Conflict, ...]
    unresolved: tuple[str, ...]
    unknown: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class RunReport:
    """One orchestration, end to end, with the call count on the face of it."""

    question: str
    subtasks: tuple[Subtask, ...]
    results: tuple[WorkerResult, ...]
    aggregate: Aggregate
    model_calls: int


class PlanError(ValueError):
    """The plan cannot be executed as written. Raised before any worker runs."""


_WORD = re.compile(r"[a-z0-9']+")

PLAN_SYSTEM = (
    "Split the user's question into independent subtasks. Each subtask must be "
    "answerable on its own, with no reference to any other subtask.\n"
    'Answer with JSON only: {"subtasks": [{"id": "...", "goal": "...", '
    '"key": "...", "depends_on": []}]}'
)


def goal_fingerprint(goal: str) -> frozenset[str]:
    """The goal's word tokens, order dropped, for spotting redundant work."""
    return frozenset(_WORD.findall((goal or "").lower()))


def parse_plan(content: str) -> list[Subtask]:
    """Shape only. Whether the plan is sane is plan_problems' job."""
    if not isinstance(content, str):
        raise PlanError(f"planner returned {type(content).__name__}, expected text")
    try:
        payload = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise PlanError(f"planner reply is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlanError(f"expected a JSON object, got {type(payload).__name__}")

    entries = payload.get("subtasks")
    if not isinstance(entries, list):
        raise PlanError("planner reply has no 'subtasks' list")

    subtasks = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise PlanError(f"subtask {position} is {type(entry).__name__}, not an object")
        values = {}
        for name in ("id", "goal", "key"):
            value = entry.get(name)
            if not isinstance(value, str) or not value.strip():
                raise PlanError(f"subtask {position} has a missing or blank {name!r}")
            values[name] = value.strip()

        depends_on = entry.get("depends_on", [])
        if not isinstance(depends_on, list) or any(
            not isinstance(item, str) for item in depends_on
        ):
            raise PlanError(
                f"subtask {values['id']!r} has a depends_on that is not a list of ids"
            )
        subtasks.append(Subtask(depends_on=tuple(depends_on), **values))
    return subtasks


def plan_problems(subtasks: list[Subtask], *, max_workers: int) -> list[str]:
    """Everything wrong with a plan that parsed, as sentences, sorted."""
    problems = []

    if not subtasks:
        problems.append("the plan is empty, so there is nothing to fan out to")

    ids = [task.id for task in subtasks]
    for duplicate in sorted({name for name in ids if ids.count(name) > 1}):
        problems.append(f"subtask id {duplicate!r} appears more than once")

    # Compare every pair once. Plans are small; this is not the hot path, and a
    # fingerprint index would hide which two subtasks collided.
    for first in range(len(subtasks)):
        for second in range(first + 1, len(subtasks)):
            a, b = subtasks[first], subtasks[second]
            if goal_fingerprint(a.goal) == goal_fingerprint(b.goal):
                problems.append(
                    f"subtasks {a.id!r} and {b.id!r} have the same goal, so one "
                    f"answer would be paid for twice"
                )

    for task in subtasks:
        if task.depends_on:
            problems.append(
                f"subtask {task.id!r} depends on "
                f"{', '.join(repr(name) for name in task.depends_on)}, so it cannot "
                f"run in parallel: this plan is a pipeline"
            )

    if len(subtasks) > max_workers:
        problems.append(
            f"the plan has {len(subtasks)} subtasks and the cap is {max_workers}, "
            f"which is {len(subtasks)} conversations rather than {max_workers}"
        )

    return sorted(problems)


def run_worker(client: Any, subtask: Subtask, *, system: str) -> WorkerResult:
    """One worker, one subtask, one clean context, and no exceptions out."""
    # Two messages, and the second is this subtask's goal alone. Anything else
    # in here is another worker's context leaking into this one.
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": subtask.goal},
    ]

    def failed(note: str) -> WorkerResult:
        return WorkerResult(subtask_id=subtask.id, status="failed", note=note)

    try:
        response = client.chat.completions.create(model="mock", messages=messages)
    except APIError as exc:
        # Caught here rather than at the orchestrator, so the other workers keep
        # the answers they already paid for. Against a real client this widens
        # to the provider's error base class, which also covers timeouts and
        # connection failures. What it must not become is a bare `except`, which
        # would swallow the bugs in your own loop along with the provider's.
        return failed(f"call failed: {exc}")

    content = response.choices[0].message.content
    try:
        payload = json.loads(content if isinstance(content, str) else "")
    except (ValueError, TypeError) as exc:
        return failed(f"reply is not JSON: {exc}")
    if not isinstance(payload, dict):
        return failed(f"expected a JSON object, got {type(payload).__name__}")

    key = payload.get("key")
    if key != subtask.key:
        return failed(
            f"answered key {key!r}, was asked for {subtask.key!r}"
        )

    value = payload.get("value") or ""
    evidence = payload.get("evidence") or ""
    confidence = payload.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.0

    if not isinstance(value, str) or not isinstance(evidence, str):
        return failed("'value' and 'evidence' must be strings")
    if not value.strip() or not evidence.strip():
        # A claim with no evidence is not a finding, whatever confidence it
        # carries. Treating it as one is how an unsourced number reaches a
        # report with a citation-shaped hole where its source should be.
        return WorkerResult(
            subtask_id=subtask.id,
            status="unknown",
            key=subtask.key,
            note="no value, or a value with no evidence",
        )

    return WorkerResult(
        subtask_id=subtask.id,
        status="ok",
        key=subtask.key,
        value=value.strip(),
        confidence=confidence,
        evidence=evidence.strip(),
    )


def aggregate(results: list[WorkerResult]) -> Aggregate:
    """Settle what agrees, adjudicate what does not, and admit what does not settle."""
    by_key: dict[str, list[WorkerResult]] = {}
    unknown, failed = [], []
    for result in results:
        if result.status == "ok":
            by_key.setdefault(result.key, []).append(result)
        elif result.status == "unknown":
            unknown.append(result.subtask_id)
        else:
            failed.append(result.subtask_id)

    findings: dict[str, str] = {}
    conflicts, unresolved = [], []

    for key in sorted(by_key):
        claims = by_key[key]
        values = {claim.value for claim in claims}
        if len(values) == 1:
            findings[key] = claims[0].value
            continue

        # Score each distinct value by the best confidence anybody gave it, not
        # by how many workers said it. Three workers reading the same wrong
        # source is one wrong source, counted three times.
        best_for_value = {
            value: max(c.confidence for c in claims if c.value == value)
            for value in values
        }
        ranked = sorted(best_for_value.items(), key=lambda pair: (-pair[1], pair[0]))
        winner = ranked[0][0] if ranked[0][1] > ranked[1][1] else None

        if winner is None:
            unresolved.append(key)
        else:
            findings[key] = winner

        conflicts.append(
            Conflict(
                key=key,
                claims=tuple(
                    (c.subtask_id, c.value, c.confidence)
                    for c in sorted(claims, key=lambda c: (-c.confidence, c.subtask_id))
                ),
                winner=winner,
            )
        )

    return Aggregate(
        findings=findings,
        conflicts=tuple(conflicts),
        unresolved=tuple(sorted(unresolved)),
        unknown=tuple(sorted(unknown)),
        failed=tuple(sorted(failed)),
    )


class Orchestrator:
    """Plans, fans out, aggregates. Owns the plan and nothing else."""

    def __init__(
        self,
        client: Any,
        *,
        worker_system: str,
        max_workers: int = 4,
    ) -> None:
        self.client = client
        self.worker_system = worker_system
        self.max_workers = max_workers

    def plan(self, question: str) -> list[Subtask]:
        """One call, parsed, then checked before a single worker is paid for."""
        response = self.client.chat.completions.create(
            model="mock",
            messages=[
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": question},
            ],
        )
        subtasks = parse_plan(response.choices[0].message.content)

        problems = plan_problems(subtasks, max_workers=self.max_workers)
        if problems:
            # Every problem at once. Reporting the first one turns fixing a plan
            # into a call per problem.
            raise PlanError("; ".join(problems))
        return subtasks

    def run(self, question: str) -> RunReport:
        """Plan, fan out, aggregate. The call count comes back on the report."""
        subtasks = self.plan(question)
        results = [
            run_worker(self.client, subtask, system=self.worker_system)
            for subtask in subtasks
        ]
        return RunReport(
            question=question,
            subtasks=tuple(subtasks),
            results=tuple(results),
            aggregate=aggregate(results),
            model_calls=1 + len(subtasks),
        )
