"""
Tests for: measuring a prompt.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Case,
    CaseResult,
    EvalResult,
    compare,
    contains_all,
    exact_match,
    matches_schema,
    rejects,
    run_eval,
)

ORDER_SPEC = {"label": "string", "quantity": "integer"}


def prompt_v1(case_input: str) -> list[dict]:
    """The prompt version under test. Two versions are two of these."""
    return [
        {"role": "system", "content": "Label the ticket."},
        {"role": "user", "content": case_input},
    ]


def result(name: str, passed: bool) -> CaseResult:
    """A CaseResult with the outcome the comparison tests care about."""
    return CaseResult(name=name, output="", failures=[] if passed else ["nope"])


def run(*outcomes: tuple[str, bool]) -> EvalResult:
    """An EvalResult over named cases with fixed outcomes."""
    results = [result(name, passed) for name, passed in outcomes]
    rate = round(sum(1 for r in results if r.passed) / len(results), 2) if results else 0.0
    return EvalResult(results=results, pass_rate=rate)


class TestGraders(unittest.TestCase):
    def test_exact_match_accepts_the_expected_value(self):
        self.assertIsNone(exact_match("billing")("billing"))

    def test_exact_match_strips_surrounding_whitespace(self):
        self.assertIsNone(
            exact_match("billing")("  billing\n"),
            "a trailing newline is not a failure worth reporting",
        )

    def test_exact_match_is_case_sensitive(self):
        self.assertIsNotNone(exact_match("billing")("Billing"))

    def test_exact_match_reason_names_both_sides(self):
        reason = exact_match("billing")("Billing.")
        self.assertIn("billing", reason)
        self.assertIn("Billing.", reason, "the reason has to say what came back")

    def test_contains_all_accepts_when_every_term_appears(self):
        self.assertIsNone(contains_all(["A-1044", "refund"])("Refund issued for A-1044."))

    def test_contains_all_is_case_insensitive(self):
        self.assertIsNone(contains_all(["REFUND"])("a refund is on its way"))

    def test_contains_all_reports_every_missing_term(self):
        reason = contains_all(["A-1044", "refund", "shipped"])("Refund issued.")
        self.assertIn("A-1044", reason)
        self.assertIn("shipped", reason, "report all the missing terms, not just the first")
        self.assertNotIn("refund'", reason)

    def test_rejects_accepts_when_the_term_is_absent(self):
        self.assertIsNone(rejects("guarantee")("I cannot promise a date."))

    def test_rejects_fails_case_insensitively(self):
        self.assertIsNotNone(rejects("guarantee")("I GUARANTEE it will arrive."))

    def test_matches_schema_accepts_a_valid_object(self):
        self.assertIsNone(matches_schema(ORDER_SPEC)('{"label": "billing", "quantity": 2}'))

    def test_matches_schema_rejects_a_code_fence(self):
        reason = matches_schema(ORDER_SPEC)('```json\n{"label": "a", "quantity": 1}\n```')
        self.assertIsNotNone(
            reason,
            "a grader that digs JSON out of a fence hides the fact that the prompt "
            "is producing fences",
        )

    def test_matches_schema_rejects_a_json_array(self):
        self.assertIsNotNone(matches_schema(ORDER_SPEC)("[1, 2]"))

    def test_matches_schema_reports_a_missing_field(self):
        reason = matches_schema(ORDER_SPEC)('{"label": "billing"}')
        self.assertIn("quantity", reason)

    def test_matches_schema_reports_a_wrong_type(self):
        reason = matches_schema(ORDER_SPEC)('{"label": "billing", "quantity": "two"}')
        self.assertIn("quantity", reason)

    def test_matches_schema_does_not_accept_bool_as_integer(self):
        self.assertIsNotNone(
            matches_schema(ORDER_SPEC)('{"label": "billing", "quantity": true}'),
            "bool is a subclass of int, so a naive isinstance check lets true through",
        )


class TestRunEval(unittest.TestCase):
    def setUp(self):
        self.cases = [
            Case("double charge", "I was charged twice.", [exact_match("billing")]),
            Case("crash", "The app crashes.", [exact_match("bug")]),
        ]

    def test_pass_rate_when_everything_passes(self):
        client = MockClient([text("billing"), text("bug")])
        self.assertEqual(run_eval(client, prompt_v1, self.cases).pass_rate, 1.0)

    def test_pass_rate_when_half_the_suite_fails(self):
        client = MockClient([text("billing"), text("billing")])
        self.assertEqual(run_eval(client, prompt_v1, self.cases).pass_rate, 0.5)

    def test_cases_run_in_the_order_given(self):
        client = MockClient([text("bug"), text("billing")])
        outcome = run_eval(client, prompt_v1, self.cases)
        self.assertEqual(
            outcome.pass_rate,
            0.0,
            "the scripted client hands out replies in sequence, so running the "
            "cases out of order silently pairs each output with the wrong case",
        )

    def test_one_model_call_per_case(self):
        client = MockClient([text("billing"), text("bug")])
        run_eval(client, prompt_v1, self.cases)
        self.assertEqual(client.call_count, 2)

    def test_sends_what_prompt_fn_built(self):
        client = MockClient([text("billing"), text("bug")])
        run_eval(client, prompt_v1, self.cases)
        self.assertEqual(
            client.requests[0]["messages"],
            prompt_v1("I was charged twice."),
            "prompt_fn is the version under test; nothing else may edit the messages",
        )

    def test_keeps_the_output_of_each_case(self):
        client = MockClient([text("billing"), text("nonsense")])
        outcome = run_eval(client, prompt_v1, self.cases)
        self.assertEqual([r.output for r in outcome.results], ["billing", "nonsense"])

    def test_a_case_fails_when_any_one_grader_fails(self):
        cases = [Case("mixed", "x", [contains_all(["ok"]), rejects("sorry")])]
        client = MockClient([text("ok, sorry about that")])
        outcome = run_eval(client, prompt_v1, cases)
        self.assertFalse(outcome.results[0].passed)
        self.assertEqual(outcome.pass_rate, 0.0)

    def test_every_grader_runs_and_every_reason_is_kept(self):
        cases = [Case("both", "x", [exact_match("billing"), contains_all(["A-1"])])]
        client = MockClient([text("no idea")])
        outcome = run_eval(client, prompt_v1, cases)
        self.assertEqual(
            len(outcome.results[0].failures),
            2,
            "run every grader: three reasons on one case is three things to fix",
        )

    def test_an_empty_suite_scores_zero(self):
        client = MockClient([text("billing")])
        outcome = run_eval(client, prompt_v1, [])
        self.assertEqual(outcome.results, [])
        self.assertEqual(
            outcome.pass_rate,
            0.0,
            "an empty suite is not a pass, or a misconfigured runner reports "
            "success forever",
        )
        self.assertEqual(client.call_count, 0)


class TestCompare(unittest.TestCase):
    def test_names_the_regressed_cases(self):
        outcome = compare(run(("a", True), ("b", True)), run(("a", True), ("b", False)))
        self.assertEqual(outcome.regressed, ["b"])
        self.assertEqual(outcome.improved, [])

    def test_names_the_improved_cases(self):
        outcome = compare(run(("a", False), ("b", True)), run(("a", True), ("b", True)))
        self.assertEqual(outcome.improved, ["a"])
        self.assertEqual(outcome.regressed, [])

    def test_a_clean_improvement_is_better(self):
        outcome = compare(run(("a", False), ("b", True)), run(("a", True), ("b", True)))
        self.assertTrue(outcome.better)
        self.assertEqual(outcome.pass_rate_delta, 0.5)

    def test_a_regression_is_not_better_even_at_a_higher_pass_rate(self):
        outcome = compare(
            run(("a", True), ("b", False), ("c", False)),
            run(("a", False), ("b", True), ("c", True)),
        )
        self.assertGreater(outcome.pass_rate_delta, 0)
        self.assertEqual(outcome.regressed, ["a"])
        self.assertFalse(
            outcome.better,
            "trading a working case away is a decision somebody makes with the case "
            "in front of them, not one an average makes for them",
        )

    def test_no_change_is_not_better(self):
        outcome = compare(run(("a", True), ("b", False)), run(("a", True), ("b", False)))
        self.assertFalse(outcome.better)
        self.assertEqual(outcome.pass_rate_delta, 0.0)

    def test_different_case_sets_raise(self):
        with self.assertRaises(ValueError):
            compare(run(("a", True), ("b", True)), run(("a", True)))

    def test_reordered_cases_raise(self):
        with self.assertRaises(
            ValueError,
            msg="same names in a different order is still not the same suite",
        ):
            compare(run(("a", True), ("b", True)), run(("b", True), ("a", True)))

    def test_end_to_end_against_two_scripted_versions(self):
        cases = [
            Case("double charge", "I was charged twice.", [exact_match("billing")]),
            Case("chargeback", "I filed a chargeback.", [exact_match("escalation")]),
        ]
        baseline = run_eval(MockClient([text("billing"), text("billing")]), prompt_v1, cases)
        candidate = run_eval(
            MockClient([text("escalation"), text("escalation")]), prompt_v1, cases
        )

        outcome = compare(baseline, candidate)
        self.assertEqual(outcome.regressed, ["double charge"])
        self.assertEqual(outcome.improved, ["chargeback"])
        self.assertFalse(
            outcome.better,
            "the classic bad fix: the new rule fixes the case that motivated it and "
            "breaks one nobody looked at",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
