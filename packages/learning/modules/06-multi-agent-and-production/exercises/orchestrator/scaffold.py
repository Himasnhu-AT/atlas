"""
An orchestrator and its workers.

One component owns the plan. Every other component owns one bounded task and
knows nothing about the others. The interesting code is not the fan out, which
is a loop: it is checking that the plan can be fanned out at all, and deciding
what to believe when two workers come back disagreeing.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from mockllm import APIError


@dataclass(frozen=True)
class Subtask:
    """
    One unit of work handed to one worker.

    Attributes:
        id: unique within a plan. It is what every result and every conflict is
            traced back to.
        goal: what this worker is asked to do, in its own words, with no
            reference to any other subtask.
        key: the single fact this subtask must establish. Two subtasks may share
            a key on purpose, which is how you cross-check an important number
            against a second source.
        depends_on: ids this subtask needs the output of. Any value here means
            the plan is a pipeline and not a fan out, which plan_problems will
            tell you about.
    """

    id: str
    goal: str
    key: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerResult:
    """
    What one worker returns.

    Structured rather than prose, and not for tidiness: the orchestrator has to
    compare two workers' answers, and comparing two paragraphs means either a
    second model call or a regular expression you will regret.

    Attributes:
        subtask_id: which subtask this answers.
        status: "ok", "unknown" or "failed". "unknown" is the worker doing its
            job and finding nothing; "failed" is the worker or the provider
            breaking.
        key: the fact answered. On an "ok" result this equals the subtask's key.
        value: the answer, "" unless the status is "ok".
        confidence: 0.0 to 1.0 as reported by the worker.
        evidence: where the value came from. An "ok" result always has some.
        note: why a result is not "ok". Empty otherwise.
    """

    subtask_id: str
    status: str
    key: str = ""
    value: str = ""
    confidence: float = 0.0
    evidence: str = ""
    note: str = ""


@dataclass(frozen=True)
class Conflict:
    """
    Two or more workers answered the same key differently.

    Attributes:
        key: the contested fact.
        claims: (subtask_id, value, confidence) for every "ok" result on this
            key, sorted by confidence descending then subtask id ascending.
        winner: the value the aggregate accepted, or None when nothing separated
            the top two and a person has to look.
    """

    key: str
    claims: tuple[tuple[str, str, float], ...]
    winner: str | None


@dataclass(frozen=True)
class Aggregate:
    """
    What the run actually established.

    Attributes:
        findings: key to accepted value, for every key that settled.
        conflicts: every contested key, including the ones that settled, because
            "we picked the higher confidence answer" is a fact about the run
            that belongs in the report.
        unresolved: keys that were contested and did not settle, sorted.
        unknown: subtask ids whose worker found nothing, sorted.
        failed: subtask ids whose worker broke, sorted.
    """

    findings: dict[str, str]
    conflicts: tuple[Conflict, ...]
    unresolved: tuple[str, ...]
    unknown: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class RunReport:
    """
    One orchestration, end to end.

    `model_calls` is one for the plan plus one per worker. It is on the report
    rather than in a log because the number is a design parameter: a plan with
    six subtasks is six conversations, and you want to see that while you are
    choosing how many subtasks to allow.
    """

    question: str
    subtasks: tuple[Subtask, ...]
    results: tuple[WorkerResult, ...]
    aggregate: Aggregate
    model_calls: int


class PlanError(ValueError):
    """
    The plan cannot be executed as written.

    Raised before any worker runs. That timing is the point: an unfannable plan
    caught at planning time costs one call, and caught after the fan out costs
    one per subtask plus a report nobody can trust.
    """


_WORD = re.compile(r"[a-z0-9']+")

PLAN_SYSTEM = (
    "Split the user's question into independent subtasks. Each subtask must be "
    "answerable on its own, with no reference to any other subtask.\n"
    'Answer with JSON only: {"subtasks": [{"id": "...", "goal": "...", '
    '"key": "...", "depends_on": []}]}'
)


def goal_fingerprint(goal: str) -> frozenset[str]:
    """
    A comparable shape for a subtask's goal.

    The lowercase word tokens of the goal, as a frozenset. Word order is dropped
    deliberately: "revenue in 2024" and "2024 revenue" are one piece of work
    phrased twice, and a planner that emits both has spent two workers on one
    answer.
    """
    raise NotImplementedError


def parse_plan(content: str) -> list[Subtask]:
    """
    Read a plan out of the planner's reply.

    The expected reply is a JSON object with a "subtasks" list, each entry an
    object with string "id", "goal" and "key", and an optional "depends_on" list
    of strings.

    Returns:
        The subtasks in the order given, with depends_on as a tuple.

    Raises:
        PlanError: the content is not JSON, is not an object, has no "subtasks"
            list, or an entry is not an object, is missing any of id, goal or
            key, has a blank one, or has a depends_on that is not a list of
            strings.

        This function validates shape only. Whether the plan makes sense is
        plan_problems' job, and keeping the two apart is what lets you report
        "the planner returned prose" differently from "the planner returned a
        pipeline".
    """
    raise NotImplementedError


def plan_problems(subtasks: list[Subtask], *, max_workers: int) -> list[str]:
    """
    Everything wrong with a plan that parsed.

    Four checks, and each one is a real failure people ship:

        duplicate ids           results cannot be traced back to a subtask
        overlapping goals       two subtasks with the same goal_fingerprint,
                                which is one answer bought twice
        a non-empty depends_on  the subtask needs another's output, so this is a
                                pipeline and cannot be run in parallel
        too many subtasks       len(subtasks) > max_workers

    An empty plan is also a problem: the planner produced nothing usable and
    fanning out to zero workers gives you a confident empty report.

    Word the sentences however you like, but each one must contain the values
    that identify what to fix, because a problem naming no subtask sends the
    reader back to the plan to work out which one it meant:

        duplicate ids       the repeated id
        overlapping goals   both subtask ids
        a dependency        the dependent id and every id it depends on
        too many subtasks   both numbers, the subtask count and max_workers

    Returns:
        The problems as sentences, sorted, so a caller comparing two plans sees
        a stable list. Empty means the plan can be run.
    """
    raise NotImplementedError


def run_worker(client: Any, subtask: Subtask, *, system: str) -> WorkerResult:
    """
    Run one worker, in isolation, and never raise.

    Send exactly two messages: the system prompt, then the subtask's goal and
    nothing else. No other subtask's goal, no other worker's findings, no
    running summary. The moment another subtask's text is in this prompt, the
    workers stop being independent: you are paying n times to ask n variations
    of the same wide question.

    The reply is expected to be a JSON object with "key", "value", "confidence"
    and "evidence".

    Returns a WorkerResult, and never propagates an APIError, because one worker
    failing is a fact about that subtask and not the end of the run:

        the call raised APIError    status "failed", note naming the error
        the reply did not parse     status "failed", note naming the parse error
        the reply's key is not the
            subtask's key           status "failed", note containing both keys,
                                    the one answered and the one asked for
        value or evidence is blank  status "unknown"
        otherwise                   status "ok"

    A "failed" result always carries a non-empty note. A failure you cannot read
    is a failure you cannot fix.

    The key check is the one worth sitting with. A structured result can be
    compared against the request that produced it, so a worker that wandered off
    and answered a different question is caught here for free. Prose cannot be
    checked this way, which is most of why workers return structure.
    """
    raise NotImplementedError


def aggregate(results: list[WorkerResult]) -> Aggregate:
    """
    Decide what the run established.

    Group every "ok" result by key. A key with one distinct value is settled.
    A key with two or more distinct values is a Conflict, and somebody has to
    decide:

        take the best confidence reported for each distinct value
        sort the values by that confidence, descending, then by value ascending
        if the top value's best confidence is strictly greater than the next
            value's, it wins and lands in findings
        otherwise the key is unresolved: it is left out of findings entirely and
            named in `unresolved`

    Ties do not go to the first worker, or to the longest answer, or to the
    orchestrator's judgement. Nothing separated them, so the honest output is
    that this run did not establish the fact. A guessed winner in `findings` is
    indistinguishable from a real one two layers downstream.

    Conflicts are reported for every contested key, settled or not, sorted by
    key. `unknown` and `failed` collect the subtask ids of the results that were
    not "ok", each sorted.
    """
    raise NotImplementedError


class Orchestrator:
    """
    Plans, fans out, aggregates.

    Attributes:
        client: a mockllm.MockClient.
        worker_system: the system prompt every worker gets. One prompt for all
            of them, because what makes workers different here is their goal and
            not their instructions.
        max_workers: the cap the plan is checked against.
    """

    def __init__(
        self,
        client: Any,
        *,
        worker_system: str,
        max_workers: int = 4,
    ) -> None:
        """Build an orchestrator. Nothing is called until run()."""
        raise NotImplementedError

    def plan(self, question: str) -> list[Subtask]:
        """
        One model call, parsed and checked.

        Send PLAN_SYSTEM and then the question as two messages, parse the reply,
        and check it.

        Raises:
            PlanError: from parse_plan, or when plan_problems is non-empty, with
                every problem in the message so one look tells you all of them.
        """
        raise NotImplementedError

    def run(self, question: str) -> RunReport:
        """
        Plan, run every worker, aggregate.

        Workers run in the plan's order. Nothing is shared between them and no
        worker sees another's result.

        Returns:
            A RunReport whose model_calls is 1 + len(subtasks).

        Raises:
            PlanError: the plan did not survive plan(). One call spent, no
                workers run.
        """
        raise NotImplementedError
