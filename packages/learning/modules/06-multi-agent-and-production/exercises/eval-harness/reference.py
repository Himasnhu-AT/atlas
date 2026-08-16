"""
An eval harness for an agent: worked solution.

Two families of assertion over one trajectory, a suite that names the assertion
that failed, and a gate that treats any regression as a failure whatever the
aggregate did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mockllm import MockClient


@dataclass(frozen=True)
class Step:
    """One tool call the agent made. Recorded whether or not it worked."""

    tool: str
    arguments: dict
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class Trajectory:
    """The answer, the tool calls in order, and why the run stopped."""

    output: str
    steps: tuple[Step, ...]
    stop: str


def run_agent(
    client: Any,
    tools: dict[str, Callable[[dict], str]],
    question: str,
    *,
    max_steps: int = 6,
) -> Trajectory:
    """The agent under test. Complete, and not part of the exercise."""
    messages: list[dict] = [{"role": "user", "content": question}]
    steps: list[Step] = []

    for _ in range(max_steps):
        try:
            response = client.chat.completions.create(model="mock", messages=messages)
        except Exception:
            return Trajectory(output="", steps=tuple(steps), stop="error")

        choice = response.choices[0]
        if choice.finish_reason != "tool_calls":
            return Trajectory(
                output=choice.message.content or "", steps=tuple(steps), stop="answered"
            )

        messages.append({"role": "assistant", "content": choice.message.content or ""})
        for call in choice.message.tool_calls or []:
            name = call.function.name
            try:
                arguments = call.function.parsed_arguments()
            except ValueError:
                arguments = {}

            handler = tools.get(name)
            if handler is None:
                steps.append(Step(name, arguments, ok=False, error="no such tool"))
                messages.append({"role": "tool", "content": "error: no such tool"})
                continue
            try:
                observation = handler(arguments)
                steps.append(Step(name, arguments, ok=True))
            except Exception as exc:
                steps.append(Step(name, arguments, ok=False, error=str(exc)))
                observation = f"error: {exc}"
            messages.append({"role": "tool", "content": observation})

    return Trajectory(output="", steps=tuple(steps), stop="budget")


@dataclass(frozen=True)
class Assertion:
    """A named check returning None when it holds, or a reason when it does not."""

    name: str
    check: Callable[[Trajectory], str | None]


@dataclass(frozen=True)
class Case:
    """One scripted run and what should be true of it."""

    name: str
    question: str
    script: tuple
    assertions: tuple[Assertion, ...]
    max_steps: int = 6


@dataclass(frozen=True)
class CaseResult:
    """One case's verdict, with every failing assertion named."""

    name: str
    passed: bool
    failures: tuple[tuple[str, str], ...]
    trajectory: Trajectory


@dataclass(frozen=True)
class SuiteResult:
    """A whole suite: a rate for the trend, and pairs for the person fixing it."""

    results: tuple[CaseResult, ...]
    pass_rate: float
    failures: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GateResult:
    """The decision about whether a change ships."""

    ok: bool
    pass_rate: float
    regressions: tuple[str, ...]
    fixed: tuple[str, ...]
    reason: str


# Outcome assertions. What the agent said.


def output_contains(fragment: str) -> Assertion:
    """The final answer contains `fragment`."""

    def check(trajectory: Trajectory) -> str | None:
        if fragment in trajectory.output:
            return None
        return f"output was {trajectory.output!r}"

    return Assertion(name=f"output_contains({fragment!r})", check=check)


def stopped_with(reason: str) -> Assertion:
    """The run ended for the given reason."""

    def check(trajectory: Trajectory) -> str | None:
        if trajectory.stop == reason:
            return None
        return f"stopped with {trajectory.stop!r}"

    return Assertion(name=f"stopped_with({reason!r})", check=check)


# Trajectory assertions. What the agent did on the way.


def called(tool: str) -> Assertion:
    """The agent reached for `tool` at least once, working or not."""

    def check(trajectory: Trajectory) -> str | None:
        if any(step.tool == tool for step in trajectory.steps):
            return None
        called_tools = [step.tool for step in trajectory.steps]
        return f"tools called were {called_tools}"

    return Assertion(name=f"called({tool!r})", check=check)


def never_called(tool: str) -> Assertion:
    """The agent never reached for `tool`. The assertion that pays for the harness."""

    def check(trajectory: Trajectory) -> str | None:
        indexes = [i for i, step in enumerate(trajectory.steps) if step.tool == tool]
        if not indexes:
            return None
        # Both numbers, because one accidental call and a loop of them are
        # different bugs with different fixes.
        return f"called {len(indexes)} time(s), at step index(es) {indexes}"

    return Assertion(name=f"never_called({tool!r})", check=check)


def called_in_order(*tools: str) -> Assertion:
    """These tools appear in this relative order, as a subsequence."""

    def check(trajectory: Trajectory) -> str | None:
        wanted = list(tools)
        cursor = 0
        for step in trajectory.steps:
            if cursor < len(wanted) and step.tool == wanted[cursor]:
                cursor += 1
        if cursor == len(wanted):
            return None
        # wanted[cursor] is the one the walk never got to, so say that. Naming
        # it as the tool it "reached" points the reader at the wrong end.
        return (
            f"never reached {wanted[cursor]!r}, position {cursor} of the order; "
            f"tools called were {[step.tool for step in trajectory.steps]}"
        )

    return Assertion(name=f"called_in_order({', '.join(tools)})", check=check)


def at_most_steps(limit: int) -> Assertion:
    """No more than `limit` tool calls."""

    def check(trajectory: Trajectory) -> str | None:
        if len(trajectory.steps) <= limit:
            return None
        return f"took {len(trajectory.steps)} steps"

    return Assertion(name=f"at_most_steps({limit})", check=check)


# Running them.


def run_case(case: Case, tools: dict[str, Callable[[dict], str]]) -> CaseResult:
    """Run one case against a fresh client and grade every assertion."""
    # Fresh client per case. A shared one carries its cursor from the previous
    # case, so the suite passes in one order and fails in another.
    client = MockClient(list(case.script))
    trajectory = run_agent(client, tools, case.question, max_steps=case.max_steps)

    failures = []
    for assertion in case.assertions:
        # Every assertion runs, including the ones after the first failure. The
        # first run of a broken change should tell you everything it broke.
        reason = assertion.check(trajectory)
        if reason is not None:
            failures.append((assertion.name, reason))

    return CaseResult(
        name=case.name,
        passed=not failures,
        failures=tuple(failures),
        trajectory=trajectory,
    )


def run_suite(
    cases: list[Case], tools: dict[str, Callable[[dict], str]]
) -> SuiteResult:
    """Run every case, in order, and report both the rate and the pairs."""
    names = [case.name for case in cases]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(
            f"duplicate case name(s): {', '.join(duplicates)}. The baseline is "
            f"keyed by name, so a duplicate quietly loses a case."
        )

    results = [run_case(case, tools) for case in cases]
    passed = sum(1 for result in results if result.passed)
    failures = sorted(
        (result.name, name) for result in results for name, _ in result.failures
    )
    return SuiteResult(
        results=tuple(results),
        pass_rate=passed / len(results) if results else 0.0,
        failures=tuple(failures),
    )


def baseline_from(suite: SuiteResult) -> dict[str, bool]:
    """Case name to whether it passed. Per case, not a single number."""
    return {result.name: result.passed for result in suite.results}


def gate(
    suite: SuiteResult, baseline: dict[str, bool], *, floor: float = 0.0
) -> GateResult:
    """Any regression fails, whatever the aggregate did."""
    now = baseline_from(suite)

    # A case missing from the baseline is new. It cannot have regressed, and
    # treating it as a regression would make adding a case to the suite a
    # build failure, which is how suites stop growing.
    regressions = sorted(name for name, ok in now.items() if baseline.get(name) and not ok)
    fixed = sorted(
        name for name, ok in now.items() if name in baseline and ok and not baseline[name]
    )

    if regressions:
        reason = f"regressed: {', '.join(regressions)}"
    elif suite.pass_rate < floor:
        reason = f"pass rate {suite.pass_rate:.2f} is below the floor of {floor:.2f}"
    else:
        reason = "ok"

    return GateResult(
        ok=not regressions and suite.pass_rate >= floor,
        pass_rate=suite.pass_rate,
        regressions=tuple(regressions),
        fixed=tuple(fixed),
        reason=reason,
    )
