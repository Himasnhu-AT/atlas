"""
Tests for: an eval harness for an agent.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import error, text, tool_call

from solution import (
    Case,
    Step,
    Trajectory,
    at_most_steps,
    baseline_from,
    called,
    called_in_order,
    gate,
    never_called,
    output_contains,
    run_case,
    run_suite,
    stopped_with,
)

TOOLS = {
    "search": lambda args: f"3 results for {args.get('q', '')}",
    "summarise": lambda args: "a summary",
    "refund": lambda args: "refund issued",
    "flaky": lambda args: (_ for _ in ()).throw(RuntimeError("upstream is down")),
}


def trajectory(*tools, output="done", stop="answered"):
    """A trajectory with one successful step per named tool."""
    return Trajectory(
        output=output,
        steps=tuple(Step(tool=name, arguments={}, ok=True) for name in tools),
        stop=stop,
    )


def simple_case(name, answer, expect="ok"):
    """A one-call case that passes exactly when `expect` is in `answer`."""
    return Case(
        name=name,
        question="anything",
        script=(text(answer),),
        assertions=(output_contains(expect),),
    )


GOOD = Case(
    name="answers-from-search",
    question="how many results",
    script=(tool_call("search", {"q": "widgets"}), text("There are 3 results.")),
    assertions=(
        output_contains("3"),
        called("search"),
        never_called("refund"),
        at_most_steps(2),
        stopped_with("answered"),
    ),
)

DESTRUCTIVE = Case(
    name="refunds-without-being-asked",
    question="how many results",
    script=(tool_call("refund", {"amount": 49}), text("There are 3 results.")),
    assertions=(output_contains("3"), never_called("refund")),
)


class TestOutcomeAssertions(unittest.TestCase):
    def test_output_contains_passes(self):
        self.assertIsNone(output_contains("790").check(trajectory(output="it is 790")))

    def test_output_contains_reports_what_it_saw(self):
        reason = output_contains("790").check(trajectory(output="it is 791"))
        self.assertIn("791", reason, "the reason is the bug report; put the value in it")

    def test_output_contains_names_itself(self):
        self.assertIn("790", output_contains("790").name)

    def test_stopped_with_passes(self):
        self.assertIsNone(stopped_with("budget").check(trajectory(stop="budget")))

    def test_stopped_with_reports_the_actual_reason(self):
        reason = stopped_with("answered").check(trajectory(stop="error"))
        self.assertIn(
            "error",
            reason,
            f"the reason carries the stop reason it actually saw. Got: {reason!r}",
        )


class TestTrajectoryAssertions(unittest.TestCase):
    def test_called_finds_the_tool(self):
        self.assertIsNone(called("search").check(trajectory("search", "summarise")))

    def test_called_reports_what_was_called_instead(self):
        reason = called("search").check(trajectory("summarise"))
        self.assertIn(
            "summarise",
            reason,
            f"the reason carries the tools that were called. Got: {reason!r}",
        )

    def test_a_failed_call_still_counts_as_called(self):
        broken = Trajectory(
            output="",
            steps=(Step(tool="flaky", arguments={}, ok=False, error="upstream is down"),),
            stop="answered",
        )
        self.assertIsNone(
            called("flaky").check(broken),
            "the question is whether the agent reached for the tool, not whether "
            "the tool worked",
        )

    def test_never_called_passes_when_absent(self):
        self.assertIsNone(never_called("refund").check(trajectory("search")))

    def test_never_called_counts_the_calls(self):
        reason = never_called("refund").check(trajectory("search", "refund", "refund"))
        self.assertIn("2", reason, "once by accident and twice in a loop are different bugs")

    def test_called_in_order_allows_other_tools_between(self):
        self.assertIsNone(
            called_in_order("search", "summarise").check(
                trajectory("search", "search", "refund", "summarise")
            ),
            "a subsequence, not a contiguous run: a suite that fails on harmless "
            "variation gets switched off",
        )

    def test_called_in_order_fails_when_reversed(self):
        reason = called_in_order("search", "summarise").check(
            trajectory("summarise", "search")
        )
        self.assertIsNotNone(reason)
        self.assertIn(
            "summarise",
            reason,
            "the reason names the tool that was never reached, which is the "
            f"second one here because the walk stopped on it. Got: {reason!r}",
        )

    def test_called_in_order_fails_when_one_is_missing(self):
        self.assertIsNotNone(
            called_in_order("search", "summarise").check(trajectory("search"))
        )

    def test_at_most_steps_is_inclusive(self):
        self.assertIsNone(
            at_most_steps(2).check(trajectory("search", "summarise")),
            "at most two means two is allowed",
        )

    def test_at_most_steps_reports_the_count(self):
        reason = at_most_steps(1).check(trajectory("search", "summarise", "search"))
        self.assertIn(
            "3",
            reason,
            f"the reason carries the count it actually saw. Got: {reason!r}",
        )


class TestRunCase(unittest.TestCase):
    def test_a_clean_case_passes(self):
        result = run_case(GOOD, TOOLS)
        self.assertTrue(result.passed, result.failures)
        self.assertEqual(result.failures, ())

    def test_the_trajectory_comes_back_with_the_result(self):
        result = run_case(GOOD, TOOLS)
        self.assertEqual([step.tool for step in result.trajectory.steps], ["search"])

    def test_a_destructive_call_fails_the_case(self):
        result = run_case(DESTRUCTIVE, TOOLS)
        self.assertFalse(
            result.passed,
            "the answer was right and it issued a refund on the way; no outcome "
            "assertion would ever notice",
        )
        self.assertEqual([name for name, _ in result.failures], ["never_called('refund')"])

    def test_every_assertion_runs_after_the_first_failure(self):
        case = Case(
            name="two-problems",
            question="q",
            script=(tool_call("refund", {}), text("nothing useful")),
            assertions=(output_contains("3"), never_called("refund")),
        )
        result = run_case(case, TOOLS)
        self.assertEqual(
            len(result.failures),
            2,
            "the first run of a broken change should tell you everything it broke",
        )

    def test_a_failing_assertion_carries_a_reason(self):
        result = run_case(DESTRUCTIVE, TOOLS)
        self.assertNotEqual(result.failures[0][1], "")

    def test_running_the_same_case_twice_gives_the_same_answer(self):
        first = run_case(GOOD, TOOLS)
        second = run_case(GOOD, TOOLS)
        self.assertEqual(
            (first.passed, first.trajectory.output),
            (second.passed, second.trajectory.output),
            "run_case builds its own client, so a case is not consumed by running it",
        )

    def test_a_provider_failure_is_a_trajectory_not_an_exception(self):
        case = Case(
            name="provider-down",
            question="q",
            script=(error("service unavailable", 503),),
            assertions=(stopped_with("error"),),
        )
        self.assertTrue(run_case(case, TOOLS).passed)

    def test_a_runaway_loop_stops_on_budget(self):
        case = Case(
            name="runaway",
            question="q",
            script=(tool_call("search", {"q": "a"}), tool_call("search", {"q": "b"})),
            assertions=(stopped_with("budget"), at_most_steps(2)),
            max_steps=2,
        )
        self.assertTrue(run_case(case, TOOLS).passed)


class TestSuiteAndGate(unittest.TestCase):
    def suite(self, alpha, beta, gamma):
        """A three case suite whose verdicts you choose."""
        return run_suite(
            [
                simple_case("alpha", "ok" if alpha else "no"),
                simple_case("beta", "ok" if beta else "no"),
                simple_case("gamma", "ok" if gamma else "no"),
            ],
            TOOLS,
        )

    def test_pass_rate(self):
        self.assertAlmostEqual(self.suite(True, False, True).pass_rate, 2 / 3)

    def test_an_empty_suite_is_zero_not_an_error(self):
        self.assertEqual(run_suite([], TOOLS).pass_rate, 0.0)

    def test_failures_are_case_and_assertion_pairs(self):
        suite = self.suite(True, False, False)
        self.assertEqual(
            suite.failures,
            (("beta", "output_contains('ok')"), ("gamma", "output_contains('ok')")),
            "a pair names the case and the check; a pass rate names neither",
        )

    def test_duplicate_case_names_are_rejected(self):
        with self.assertRaises(ValueError):
            run_suite([simple_case("alpha", "ok"), simple_case("alpha", "no")], TOOLS)

    def test_baseline_is_per_case(self):
        self.assertEqual(
            baseline_from(self.suite(True, False, True)),
            {"alpha": True, "beta": False, "gamma": True},
        )

    def test_an_unchanged_suite_passes_the_gate(self):
        baseline = baseline_from(self.suite(True, False, True))
        result = gate(self.suite(True, False, True), baseline, floor=0.5)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, "ok")

    def test_a_regression_fails_even_when_the_rate_went_up(self):
        baseline = baseline_from(self.suite(True, False, False))
        result = gate(self.suite(False, True, True), baseline, floor=0.5)
        self.assertFalse(
            result.ok,
            "two cases fixed and one broken raises the rate and is still a "
            "regression, and the broken one is what somebody hit last week",
        )
        self.assertEqual(result.regressions, ("alpha",))
        self.assertEqual(result.fixed, ("beta", "gamma"))
        self.assertIn(
            "alpha",
            result.reason,
            "and the reason names the regressed case, because that is the line "
            f"the CI log shows somebody. Got: {result.reason!r}",
        )

    def test_a_low_rate_fails_the_gate_with_no_regression(self):
        result = gate(self.suite(False, False, True), {}, floor=0.8)
        self.assertFalse(result.ok)
        self.assertEqual(
            result.regressions,
            (),
            "nothing regressed, so this failed on the floor alone. The two "
            "conditions are reported separately because they need different fixes",
        )
        self.assertNotEqual(result.reason, "ok", "a failing gate has to say why")

    def test_a_new_failing_case_is_not_a_regression(self):
        baseline = {"alpha": True, "beta": False}
        result = gate(self.suite(True, False, False), baseline, floor=0.0)
        self.assertEqual(
            result.regressions,
            (),
            "gamma has no baseline entry, so it is new. Counting a new case as a "
            "regression is how a suite stops growing",
        )
        self.assertTrue(result.ok)

    def test_the_gate_carries_the_rate(self):
        suite = self.suite(True, True, False)
        self.assertAlmostEqual(gate(suite, {}, floor=0.0).pass_rate, suite.pass_rate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
