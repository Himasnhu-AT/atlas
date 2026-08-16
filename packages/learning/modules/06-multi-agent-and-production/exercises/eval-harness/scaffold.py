"""
An eval harness for an agent.

Grading a prompt means comparing one output to one expectation. Grading an agent
means that plus everything it did on the way, because an agent that reaches the
right answer after calling a destructive tool twice is not correct. So there are
two families of assertion here, they compose, and the suite fails on a
regression even when the aggregate number went up.

The agent itself ships with this file. Your work is the harness around it.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mockllm import MockClient


@dataclass(frozen=True)
class Step:
    """
    One tool call the agent made.

    `ok` is False when the tool raised or did not exist, and `error` says which.
    A step is recorded either way: a tool that blew up was still called, and an
    assertion about what the agent touched has to see it.
    """

    tool: str
    arguments: dict
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class Trajectory:
    """
    Everything one run did.

    Attributes:
        output: the final answer, "" when the run did not produce one.
        steps: the tool calls, in order.
        stop: "answered", "budget" when max_steps ran out, or "error" when the
            provider failed. These are three different bugs and collapsing them
            into "no answer" throws away which one you have.
    """

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
    """
    The agent under test. Complete, and not part of the exercise.

    A plain tool-calling loop: ask the model, run whatever it asked for, feed
    the result back, stop when it answers or the budget runs out.
    """
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
    """
    One named check over a trajectory.

    Attributes:
        name: what appears in the failure report. Make it specific enough to act
            on: "never_called(delete_account)" is a bug report and "trajectory"
            is a mood.
        check: called with the trajectory. Returns None when the assertion
            holds, or a sentence saying what was seen instead.

    Returning a reason rather than a bool is what lets a failing suite tell you
    the agent called the tool four times instead of "assertion failed". Word the
    reasons however you like, but every one of them has to contain the value it
    rejected: the output, the stop reason, the tools that were called, the
    count. The reason is what somebody reads at three in the morning, and a
    reason with no value in it sends them back to reproduce the run by hand.
    """

    name: str
    check: Callable[[Trajectory], str | None]


@dataclass(frozen=True)
class Case:
    """
    One scripted run and what should be true of it.

    Attributes:
        name: unique in a suite. It is the key the baseline is stored under, so
            renaming a case looks like deleting one and adding another.
        question: what the agent is asked.
        script: the mockllm steps for this case, built with text(), tool_call()
            and error(). run_case builds a fresh client from these every time,
            so a case can be run twice and give the same answer twice.
        assertions: outcome and trajectory assertions, in any order.
        max_steps: the agent's budget for this case.
    """

    name: str
    question: str
    script: tuple
    assertions: tuple[Assertion, ...]
    max_steps: int = 6


@dataclass(frozen=True)
class CaseResult:
    """
    One case's verdict.

    `failures` is (assertion name, reason) pairs in the order the assertions
    were declared. Every assertion runs even after one has failed, because
    "output was wrong and it also deleted the account" is two facts and you want
    both on the first run.
    """

    name: str
    passed: bool
    failures: tuple[tuple[str, str], ...]
    trajectory: Trajectory


@dataclass(frozen=True)
class SuiteResult:
    """
    A whole suite.

    `pass_rate` is cases passed over cases run, and it is for the trend line.
    `failures` is (case name, assertion name) pairs, sorted, and it is for the
    person who has to fix it.
    """

    results: tuple[CaseResult, ...]
    pass_rate: float
    failures: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GateResult:
    """
    The decision about whether a change ships.

    Attributes:
        ok: False if anything regressed, or if the pass rate is below the floor.
        pass_rate: the suite's rate, carried so a caller needs one object.
        regressions: case names that passed in the baseline and fail now.
        fixed: case names that failed in the baseline and pass now.
        reason: one line saying why, for the CI log.
    """

    ok: bool
    pass_rate: float
    regressions: tuple[str, ...]
    fixed: tuple[str, ...]
    reason: str


def output_contains(fragment: str) -> Assertion:
    """
    An outcome assertion: the final answer contains `fragment`.

    Case sensitive, and substring rather than equality, because the thing you
    can usually commit to is that the number appears, not the sentence around it.

    Name it f"output_contains({fragment!r})".
    """
    raise NotImplementedError


def stopped_with(reason: str) -> Assertion:
    """
    An outcome assertion: the run ended for the given reason.

    "answered", "budget" or "error". A case asserting stopped_with("budget") is
    how you pin a runaway loop you have already fixed once.

    Name it f"stopped_with({reason!r})".
    """
    raise NotImplementedError


def called(tool: str) -> Assertion:
    """
    A trajectory assertion: the agent called `tool` at least once.

    A failed call still counts as having been called. What this asks is whether
    the agent reached for the tool, not whether the tool worked.

    Name it f"called({tool!r})".
    """
    raise NotImplementedError


def never_called(tool: str) -> Assertion:
    """
    A trajectory assertion: the agent never called `tool`.

    This is the assertion that pays for the whole harness. An agent that got the
    right answer and issued a refund on the way is not correct, and no outcome
    assertion will ever notice.

    The failure reason should say how many times it was called and at which step
    indexes, because "called it once by accident" and "called it in a loop" are
    different bugs.

    Name it f"never_called({tool!r})".
    """
    raise NotImplementedError


def called_in_order(*tools: str) -> Assertion:
    """
    A trajectory assertion: these tools appear in this relative order.

    A subsequence, not a contiguous run and not the whole trajectory. Asserting
    called_in_order("search", "summarise") on a trajectory of
    [search, search, fetch, summarise] passes: the agent searched before it
    summarised, which is the property you actually care about. Requiring the
    trajectory to equal the list makes the case fail every time the agent does
    something reasonable you did not predict, and a suite that fails on harmless
    variation gets switched off.

    Walk the steps once, advancing a pointer through `tools` on each match. The
    assertion holds when the pointer reaches the end.

    The reason names the tool the pointer stopped on, which is the one that was
    never reached rather than the last one that was. Getting that backwards
    produces a message that points at the wrong end of the problem.

    Name it f"called_in_order({', '.join(tools)})".
    """
    raise NotImplementedError


def at_most_steps(limit: int) -> Assertion:
    """
    A trajectory assertion: no more than `limit` tool calls.

    Steps, not model calls. Step count is the cheapest early warning there is: a
    prompt change that makes the agent flail shows up here before it shows up in
    accuracy, and often before it shows up in the bill.

    Name it f"at_most_steps({limit})".
    """
    raise NotImplementedError


def run_case(case: Case, tools: dict[str, Callable[[dict], str]]) -> CaseResult:
    """
    Run one case and grade it.

    Build a fresh MockClient from `case.script`, run the agent with the case's
    question and max_steps, then run every assertion against the trajectory.

    Returns:
        A CaseResult. `passed` is True only when `failures` is empty.
    """
    raise NotImplementedError


def run_suite(
    cases: list[Case], tools: dict[str, Callable[[dict], str]]
) -> SuiteResult:
    """
    Run every case, in order.

    Returns:
        A SuiteResult whose pass_rate is passed / total, and 0.0 for an empty
        suite rather than a ZeroDivisionError. `failures` is every (case name,
        assertion name) pair, sorted.

    Raises:
        ValueError: two cases share a name. The baseline is keyed by name, so
            duplicates would silently grade one case twice and lose the other.
    """
    raise NotImplementedError


def baseline_from(suite: SuiteResult) -> dict[str, bool]:
    """
    The stored shape of a suite result: case name to whether it passed.

    Deliberately not the pass rate. A single number cannot tell you that two
    cases were fixed and one broke, and that is exactly the change you have to
    catch.
    """
    raise NotImplementedError


def gate(
    suite: SuiteResult, baseline: dict[str, bool], *, floor: float = 0.0
) -> GateResult:
    """
    Decide whether this suite result ships.

    A regression is a case the baseline records as passing that fails now. A fix
    is the reverse. A case with no baseline entry is new and can never be a
    regression, though it still counts toward the pass rate.

    `ok` is False when there is any regression, whatever the pass rate, and
    False when the pass rate is below the floor. Both conditions matter and
    neither substitutes for the other: a change that fixes two cases and breaks
    one raises the rate and is still a regression, and the case it broke is the
    one somebody hit in production last week.

    Returns:
        A GateResult with regressions and fixed both sorted, and a reason naming
        the regressed cases when there are any, otherwise naming the rate and
        the floor when the floor failed, otherwise "ok".
    """
    raise NotImplementedError
