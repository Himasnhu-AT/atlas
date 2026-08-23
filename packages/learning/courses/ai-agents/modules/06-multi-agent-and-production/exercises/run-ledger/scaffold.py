"""
A run ledger.

Emitting a record per step is the easy half. This is the other half: taking a
pile of those records and answering the three questions production actually
asks, which are what happened in this one run, what is failing across all runs,
and what is this costing.

Nothing here calls a model, a clock or a network. Every number is derived from
records that were handed to you, which is what makes a reporting layer testable.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

REDACTED = "[redacted]"


@dataclass(frozen=True)
class StepRecord:
    """
    One step of one run.

    Attributes:
        run_id: the id threaded through every record of a run. It is the single
            thing that makes a bug report answerable: without it you have a pile
            of steps and no way to reassemble the one the customer is describing.
        index: position within the run, from 0.
        kind: "model", "tool" or "validate". Where the step happened.
        name: the model or tool involved.
        outcome: "ok", "error", "invalid" or "aborted". What happened to it.
        detail: a short human readable note. Free text, never parsed.
        prompt_tokens, completion_tokens: usage, 0 for anything that is not a
            model call.
        payload: arguments, prompts, tool output. This is the field that will
            contain a customer's address and somebody's API key, which is why
            nothing hands it to a caller unredacted.
    """

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
    """
    One run, start to finish.

    Attributes:
        run_id: unique per run.
        task: what the run was for. Several runs can share a task, which is how
            you compare a retry to the attempt it replaced.
        status: "completed" or "failed".
        steps: the step records, in order.
        started_ms, ended_ms: milliseconds, recorded by whoever ran it. They are
            fields rather than something this module measures so that every
            number below is a function of its input and a test does not have to
            freeze time.
    """

    run_id: str
    task: str
    status: str
    steps: tuple[StepRecord, ...]
    started_ms: int = 0
    ended_ms: int = 0


@dataclass(frozen=True)
class Summary:
    """
    The rollup.

    Attributes:
        runs, completed: counts.
        total_cost: every run in the ledger, including the ones that failed. A
            failed run is not a free run.
        cost_per_completed_task: total_cost / completed. This is the number that
            means something: cost per call falls every time you add a cheap
            retry and rises every time you consolidate two calls into one, in
            both cases while telling you nothing about whether the work got
            cheaper.
        failures: bucket name to count, only for buckets that occurred.
        mean_steps_per_completed: the early warning. Step count per task climbs
            before the error rate does, because an agent that has started
            flailing still mostly succeeds, just more expensively.
        mean_duration_ms: over completed runs.
        over_budget: run ids whose step count exceeded the threshold, sorted.
    """

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
    """
    A model in the records has no entry in the price table.

    A KeyError subclass, and raised rather than treated as free, because a model
    that costs nothing is the most expensive default there is. You find out at
    the end of the month.
    """


def redact(payload: dict, secret_keys: frozenset[str]) -> dict:
    """
    A copy of `payload` with the sensitive values replaced by REDACTED.

    A key matches when its lowercase form is in `secret_keys`, which is itself
    expected to be lowercase. Recurse into nested dicts, and into dicts inside
    lists, because the interesting secrets are never at the top level.

    Args:
        payload: the recorded arguments or output.
        secret_keys: the key names to redact, lowercase. A parameter and not a
            constant, because what counts as sensitive is a property of your
            product and not of this function.

    Returns:
        A new dict. Never mutate the input: the ledger's copy is the audit
        trail, and a redaction pass that edits it in place destroys the thing it
        was protecting.

    Redaction is a requirement rather than a nicety. Once a prompt is in a log
    it is in every backup of that log, and the deletion request that arrives
    eighteen months later is somebody's whole week.
    """
    raise NotImplementedError


def classify_failure(step: StepRecord) -> str | None:
    """
    Which failure bucket a step falls into, or None when it succeeded.

    Five buckets, because these five have five different fixes and counting them
    together tells you to fix nothing:

        provider_error       kind "model", outcome "error". Retry, back off,
                             pick a fallback provider.
        tool_error           kind "tool", outcome "error". Your code or a
                             dependency of it. Fix the tool.
        malformed_tool_call  kind "model", outcome "invalid". The model emitted
                             a call that did not fit the schema. Fix the schema
                             or the prompt.
        budget_exhausted     any kind, outcome "aborted". The step budget ran
                             out. Fix the loop or raise the budget deliberately.
        output_rejected      kind "validate", outcome "invalid". The final
                             output failed its own contract. Fix the contract or
                             the prompt behind it.

    Anything else returns "unclassified". A combination you did not anticipate
    gets its own bucket rather than being dropped, because a rising count of
    failures nobody has a name for is precisely the thing you want to see.
    """
    raise NotImplementedError


def cost_of(run: RunRecord, price_table: dict[str, tuple[float, float]]) -> float:
    """
    What one run cost.

    Args:
        run: the record.
        price_table: model name to (prompt price per 1000 tokens, completion
            price per 1000 tokens). Passed in rather than hardcoded anywhere:
            prices change, they differ per provider and per contract, and a
            number baked into a reporting function is wrong within a quarter.

    Only "model" steps cost anything. A model step that errored still costs
    whatever tokens it recorded, which is usually zero for a call that never
    reached the provider and is not zero for one that timed out after
    generating.

    Returns:
        The cost, in whatever currency the table is denominated in.

    Raises:
        UnknownPrice: a model step names a model the table does not price.
    """
    raise NotImplementedError


class Ledger:
    """
    Every run, and the three questions.

    Runs are kept in insertion order, which is the order they finished. Nothing
    here is a database: it is the shape of the query layer you put in front of
    one, and writing it against a list first is how you find out which questions
    you actually need before you design a schema.
    """

    def __init__(self) -> None:
        """An empty ledger."""
        raise NotImplementedError

    def add(self, run: RunRecord) -> None:
        """
        Record a finished run.

        Raises:
            LedgerError: a run with this id is already recorded. Ingesting the
                same run twice silently doubles your cost number and halves your
                apparent error rate, and nothing about the output looks wrong.
        """
        raise NotImplementedError

    def run(self, run_id: str) -> RunRecord:
        """
        Question one: what happened in this one run.

        Raises:
            KeyError: no run with that id.
        """
        raise NotImplementedError

    def trace(self, run_id: str, *, secret_keys: frozenset[str]) -> list[StepRecord]:
        """
        The run's steps, safe to show someone.

        Every step with its payload redacted, in order. The stored records are
        not touched.

        Raises:
            KeyError: no run with that id.
        """
        raise NotImplementedError

    def failure_counts(self) -> dict[str, int]:
        """
        Question two: what is failing across all runs.

        Every step of every run, classified, counted. Buckets with a count of
        zero are left out. Keys in sorted order, so two summaries can be diffed.
        """
        raise NotImplementedError

    def summary(
        self,
        price_table: dict[str, tuple[float, float]],
        *,
        step_threshold: int = 10,
    ) -> Summary:
        """
        Question three: what is this costing, and what is about to.

        Args:
            price_table: as for cost_of.
            step_threshold: a run with strictly more steps than this is named in
                over_budget. Not an error, a smell: it is the run to read first.

        cost_per_completed_task divides by the completed count. With nothing
        completed the honest answers are math.inf when money was spent, since
        you paid and shipped nothing, and 0.0 when it was not. Neither is an
        exception: an empty ledger is a normal state on a Monday morning.

        mean_steps_per_completed and mean_duration_ms are 0.0 when nothing
        completed.
        """
        raise NotImplementedError
