"""
A run ledger: worked solution.

Records in, three answers out. Every number is a function of its input, which is
why none of this needs a clock, a network or a fixture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

REDACTED = "[redacted]"


@dataclass(frozen=True)
class StepRecord:
    """One step of one run, with the run id on it."""

    run_id: str
    index: int
    kind: str
    name: str
    outcome: str
    detail: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RunRecord:
    """One run, start to finish. Times are recorded, never measured here."""

    run_id: str
    task: str
    status: str
    steps: tuple[StepRecord, ...]
    started_ms: int = 0
    ended_ms: int = 0


@dataclass(frozen=True)
class Summary:
    """The rollup, including the two numbers worth alerting on."""

    runs: int
    completed: int
    total_cost: float
    cost_per_completed_task: float
    failures: dict[str, int]
    mean_steps_per_completed: float
    mean_duration_ms: float
    over_budget: tuple[str, ...]


class LedgerError(ValueError):
    """The ledger was asked to do something that would corrupt its numbers."""


class UnknownPrice(KeyError):
    """A model in the records has no entry in the price table."""


# (kind, outcome) to bucket. A table rather than a chain of ifs, because the
# thing you will actually do to this code is add a row to it.
_BUCKETS = {
    ("model", "error"): "provider_error",
    ("tool", "error"): "tool_error",
    ("model", "invalid"): "malformed_tool_call",
    ("validate", "invalid"): "output_rejected",
}


def redact(payload: dict, secret_keys: frozenset[str]) -> dict:
    """A copy with the sensitive values replaced, nested ones included."""

    def scrub(value):
        if isinstance(value, dict):
            return {
                key: REDACTED if key.lower() in secret_keys else scrub(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    # A new dict every time. The stored record is the audit trail, and a
    # redaction pass that edits it in place has destroyed the evidence it was
    # called to protect.
    return scrub(dict(payload))


def classify_failure(step: StepRecord) -> str | None:
    """Which bucket a failed step falls into, or None when it succeeded."""
    if step.outcome == "ok":
        return None
    if step.outcome == "aborted":
        # Kind agnostic on purpose: running out of budget is a property of the
        # loop, and which step happened to be in flight when it ran out is not
        # the interesting part.
        return "budget_exhausted"
    return _BUCKETS.get((step.kind, step.outcome), "unclassified")


def cost_of(run: RunRecord, price_table: dict[str, tuple[float, float]]) -> float:
    """Token cost of the model steps, priced by the table you pass in."""
    total = 0.0
    for step in run.steps:
        if step.kind != "model":
            continue
        if step.name not in price_table:
            raise UnknownPrice(
                f"no price for model {step.name!r} (run {run.run_id!r}, step "
                f"{step.index}). Priced models: "
                f"{', '.join(sorted(price_table)) or '(none)'}"
            )
        prompt_price, completion_price = price_table[step.name]
        total += step.prompt_tokens / 1000 * prompt_price
        total += step.completion_tokens / 1000 * completion_price
    return total


class Ledger:
    """Every run, and the three questions."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def add(self, run: RunRecord) -> None:
        """Record a finished run, once."""
        if run.run_id in self._runs:
            raise LedgerError(
                f"run {run.run_id!r} is already recorded. Ingesting it twice "
                f"doubles its cost and halves its apparent error rate, and the "
                f"output looks entirely reasonable either way."
            )
        self._runs[run.run_id] = run

    def run(self, run_id: str) -> RunRecord:
        """Question one, in its rawest form."""
        if run_id not in self._runs:
            raise KeyError(f"no run {run_id!r} in this ledger")
        return self._runs[run_id]

    def trace(self, run_id: str, *, secret_keys: frozenset[str]) -> list[StepRecord]:
        """Question one, in a form you can paste into a ticket."""
        return [
            replace(step, payload=redact(step.payload, secret_keys))
            for step in self.run(run_id).steps
        ]

    def failure_counts(self) -> dict[str, int]:
        """Question two. Sorted, so two summaries diff cleanly."""
        counts: dict[str, int] = {}
        for run in self._runs.values():
            for step in run.steps:
                bucket = classify_failure(step)
                if bucket is not None:
                    counts[bucket] = counts.get(bucket, 0) + 1
        return {bucket: counts[bucket] for bucket in sorted(counts)}

    def summary(
        self,
        price_table: dict[str, tuple[float, float]],
        *,
        step_threshold: int = 10,
    ) -> Summary:
        """Question three, plus the step count that sees trouble coming."""
        runs = list(self._runs.values())
        completed = [run for run in runs if run.status == "completed"]

        # Failed runs are charged too. They consumed tokens and produced nothing,
        # which is the worst kind of spend and the easiest to leave out of a
        # report by accident.
        total_cost = sum(cost_of(run, price_table) for run in runs)

        if completed:
            per_task = total_cost / len(completed)
            mean_steps = sum(len(run.steps) for run in completed) / len(completed)
            mean_duration = sum(
                run.ended_ms - run.started_ms for run in completed
            ) / len(completed)
        else:
            per_task = math.inf if total_cost > 0 else 0.0
            mean_steps = 0.0
            mean_duration = 0.0

        return Summary(
            runs=len(runs),
            completed=len(completed),
            total_cost=total_cost,
            cost_per_completed_task=per_task,
            failures=self.failure_counts(),
            mean_steps_per_completed=mean_steps,
            mean_duration_ms=mean_duration,
            over_budget=tuple(
                sorted(run.run_id for run in runs if len(run.steps) > step_threshold)
            ),
        )
