"""
Measuring a prompt: worked solution.

Graders that return a reason, a runner that holds everything except the prompt
constant, and a comparison that will not call a candidate better when it broke a
case that used to pass.
"""

from __future__ import annotations

import json

from dataclasses import dataclass, field
from typing import Callable

Grader = Callable[[str], str | None]

#: Schema type name to the Python types that satisfy it. bool is absent from the
#: numeric entries on purpose: it is a subclass of int, so leaving it in would
#: let `true` pass as a quantity.
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


@dataclass(frozen=True)
class Case:
    """One input and everything you expect to be true of the output."""

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
    """Two runs of the same suite, held against each other."""

    regressed: list[str] = field(default_factory=list)
    improved: list[str] = field(default_factory=list)
    pass_rate_delta: float = 0.0
    better: bool = False


def exact_match(expected: str) -> Grader:
    """Equality after stripping the ends of the output."""

    def grade(output: str) -> str | None:
        actual = output.strip()
        if actual == expected:
            return None
        return f"expected {expected!r}, got {actual!r}"

    return grade


def contains_all(terms: list[str]) -> Grader:
    """Every term present, case insensitively."""

    def grade(output: str) -> str | None:
        lowered = output.lower()
        missing = [term for term in terms if term.lower() not in lowered]
        if not missing:
            return None
        return "missing: " + ", ".join(repr(term) for term in missing)

    return grade


def rejects(term: str) -> Grader:
    """The term must not appear."""

    def grade(output: str) -> str | None:
        if term.lower() in output.lower():
            return f"contains {term!r}, which is not allowed here"
        return None

    return grade


def matches_schema(spec: dict[str, str]) -> Grader:
    """Valid JSON object with the right field types, first problem only."""

    def grade(output: str) -> str | None:
        try:
            data = json.loads(output.strip())
        except ValueError as error:
            return f"not valid JSON: {error}"

        if not isinstance(data, dict):
            return f"expected a JSON object, got {type(data).__name__}"

        for name, expected in spec.items():
            if name not in data:
                return f"missing field: {name}"

            value = data[name]
            allowed = _TYPES.get(expected)
            if allowed is None:
                return f"{name}: schema names an unknown type {expected!r}"
            # bool first. isinstance(True, int) is True, so every numeric check
            # below would otherwise accept it.
            if isinstance(value, bool) and expected != "boolean":
                return f"{name}: expected {expected}, got bool"
            if not isinstance(value, allowed):
                return f"{name}: expected {expected}, got {type(value).__name__}"

        return None

    return grade


def run_eval(client, prompt_fn, cases: list[Case]) -> EvalResult:
    """One model call per case, in order, with every grader run."""
    results: list[CaseResult] = []

    for case in cases:
        response = client.chat.completions.create(
            model="mock", messages=prompt_fn(case.input)
        )
        output = response.choices[0].message.content or ""

        # Every grader runs. Stopping at the first failure would report one
        # problem per run, and a case with three problems takes three runs to
        # understand.
        failures = [
            reason
            for reason in (grader(output) for grader in case.graders)
            if reason is not None
        ]
        results.append(CaseResult(name=case.name, output=output, failures=failures))

    if not results:
        # An empty suite is not a pass. A runner pointed at the wrong list would
        # otherwise report 1.0 forever.
        return EvalResult(results=[], pass_rate=0.0)

    passed = sum(1 for result in results if result.passed)
    return EvalResult(results=results, pass_rate=round(passed / len(results), 2))


def compare(baseline: EvalResult, candidate: EvalResult) -> Comparison:
    """Which cases moved, and whether the candidate is actually better."""
    baseline_names = [result.name for result in baseline.results]
    candidate_names = [result.name for result in candidate.results]
    if baseline_names != candidate_names:
        raise ValueError(
            "the two runs cover different cases, so they cannot be compared: "
            f"baseline has {baseline_names}, candidate has {candidate_names}"
        )

    regressed: list[str] = []
    improved: list[str] = []
    for before, after in zip(baseline.results, candidate.results):
        if before.passed and not after.passed:
            regressed.append(before.name)
        elif not before.passed and after.passed:
            improved.append(before.name)

    delta = round(candidate.pass_rate - baseline.pass_rate, 2)
    return Comparison(
        regressed=regressed,
        improved=improved,
        pass_rate_delta=delta,
        # A higher pass rate is not enough. Trading a working case away can be
        # the right call, but it is a call somebody makes with the case in front
        # of them, not one this function makes by averaging.
        better=delta > 0 and not regressed,
    )
