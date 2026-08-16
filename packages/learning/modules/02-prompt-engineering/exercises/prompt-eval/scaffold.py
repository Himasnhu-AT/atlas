"""
Measuring a prompt.

The smallest eval harness that is worth having: a handful of cases, graders with
no judgement in them, a pass rate, and a comparison between two prompt versions
that refuses to call a candidate better when it broke something.

The dataclasses below are given. You write the four graders, the runner, and the
comparison.

Run `python3 test.py` when you think you have it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

#: A grader takes the model's output and returns None when the check holds, or a
#: short reason when it does not. Returning the reason rather than False is what
#: makes a failing run a bug report instead of a number.
Grader = Callable[[str], str | None]


@dataclass(frozen=True)
class Case:
    """
    One input and everything you expect to be true of the output.

    Attributes:
        name: what a failure report prints. Make it the thing that went wrong,
            not "case 3".
        input: the text handed to the prompt under test.
        graders: every check that has to hold. All of them run, so one case can
            report several problems at once.
    """

    name: str
    input: str
    graders: list[Grader] = field(default_factory=list)


@dataclass
class CaseResult:
    """What one case produced, and every reason it failed."""

    name: str
    output: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass
class EvalResult:
    """One run of one prompt version over the suite."""

    results: list[CaseResult] = field(default_factory=list)
    pass_rate: float = 0.0


@dataclass
class Comparison:
    """
    Two runs of the same suite, held against each other.

    Attributes:
        regressed: cases that passed in the baseline and fail in the candidate.
        improved: cases that failed in the baseline and pass in the candidate.
        pass_rate_delta: candidate minus baseline, rounded to two places.
        better: whether the candidate is an improvement worth shipping.
    """

    regressed: list[str] = field(default_factory=list)
    improved: list[str] = field(default_factory=list)
    pass_rate_delta: float = 0.0
    better: bool = False


def exact_match(expected: str) -> Grader:
    """
    The output must equal `expected` exactly.

    Whitespace at either end of the output is stripped before comparing, since a
    trailing newline is not a failure anyone wants reported. Everything else is
    exact, including case.

    Returns:
        A grader. On failure the reason names both sides, because "expected
        'billing', got 'Billing.'" tells you what to fix and "no match" does not.
    """
    raise NotImplementedError


def contains_all(terms: list[str]) -> Grader:
    """
    Every term must appear somewhere in the output.

    Matching is case insensitive, because you are checking that the answer
    mentions the order id, not that it capitalised it your way.

    Returns:
        A grader whose reason lists every missing term, in the order given. All
        of them, not the first: a report naming one missing field at a time
        turns one fix into three round trips.
    """
    raise NotImplementedError


def rejects(term: str) -> Grader:
    """
    The term must NOT appear in the output. Case insensitive.

    The check that keeps a suite honest. Without at least one of these, every
    other grader rewards saying more, and a prompt that answers everything at
    length scores well while doing the wrong thing.
    """
    raise NotImplementedError


def matches_schema(spec: dict[str, str]) -> Grader:
    """
    The output must parse as a JSON object with these field types.

    `spec` maps a field name to one of "string", "integer", "number",
    "boolean", "array" or "object". Every field in the spec is required, and
    fields outside it are ignored.

    Deliberately strict about the wrapping: the output has to parse after
    stripping surrounding whitespace and nothing else. A grader that digs the
    JSON out of a code fence would hide the fact that the prompt is producing
    code fences, and hiding a failure is the one thing an eval must not do.

    Returns:
        A grader reporting the FIRST problem it finds, checking fields in the
        spec's order so the message is predictable. Remember that `bool` is a
        subclass of `int` in Python, so True must not satisfy "integer".
    """
    raise NotImplementedError


def run_eval(client, prompt_fn, cases: list[Case]) -> EvalResult:
    """
    Run one prompt version over every case.

    Args:
        client: anything with the chat completions shape.
        prompt_fn: called as prompt_fn(case.input) and returns the message list
            to send. This is the prompt version under test: two versions are two
            functions, and everything else about the run is held constant.
        cases: run in the order given, one model call each. The order is part of
            the contract, not an implementation detail, because a scripted
            client hands out its replies in sequence.

    For each case, call
    client.chat.completions.create(model="mock", messages=prompt_fn(case.input)),
    take choices[0].message.content or "" as the output, and run every grader
    against it. Collect the reasons in grader order. Run them all rather than
    stopping at the first failure: three reasons on one case is three things to
    fix, and it costs nothing.

    Returns:
        An EvalResult whose pass_rate is the fraction of cases where every
        grader held, rounded to two places. With no cases at all the pass rate
        is 0.0. An empty suite is not a pass, and treating it as one means a
        misconfigured runner reports success forever.
    """
    raise NotImplementedError


def compare(baseline: EvalResult, candidate: EvalResult) -> Comparison:
    """
    Hold two runs of the same suite against each other.

    Both results must cover the same case names in the same order. Comparing
    runs over different case sets is meaningless, and quietly intersecting them
    is how a suite starts reporting improvements that are really a case being
    dropped.

    Args:
        baseline: the run for the prompt you have.
        candidate: the run for the prompt you are considering.

    Returns:
        A Comparison. `regressed` and `improved` keep the suite's order.
        `better` is True only when the pass rate went up AND nothing regressed.

    Raises:
        ValueError: the two runs do not cover the same cases in the same order.

    The rule about regressions is the point of the whole exercise. A candidate
    that fixes two cases and breaks one has a higher pass rate and is not
    obviously an improvement: somebody has to look at the broken case and
    decide. Returning better=True there hides exactly the decision this harness
    exists to surface.
    """
    raise NotImplementedError
