"""
Tests for: a run ledger.

Run with `python3 test.py`.
"""

from __future__ import annotations

import math
import unittest

from solution import (
    REDACTED,
    Ledger,
    LedgerError,
    RunRecord,
    StepRecord,
    UnknownPrice,
    classify_failure,
    cost_of,
    redact,
)

PRICES = {"big": (0.01, 0.03), "small": (0.001, 0.002)}
SECRETS = frozenset({"api_key", "authorization", "email"})


def step(run_id, index, kind, name, outcome, prompt=0, completion=0, payload=None):
    return StepRecord(
        run_id=run_id,
        index=index,
        kind=kind,
        name=name,
        outcome=outcome,
        prompt_tokens=prompt,
        completion_tokens=completion,
        payload=payload if payload is not None else {},
    )


COMPLETED = RunRecord(
    run_id="r1",
    task="triage",
    status="completed",
    started_ms=0,
    ended_ms=1200,
    steps=(
        step("r1", 0, "model", "big", "ok", prompt=1000, completion=500),
        step("r1", 1, "tool", "search", "ok", payload={"q": "widgets"}),
        step("r1", 2, "model", "big", "ok", prompt=2000, completion=100),
    ),
)

BROKEN = RunRecord(
    run_id="r2",
    task="triage",
    status="failed",
    started_ms=0,
    ended_ms=400,
    steps=(
        step("r2", 0, "model", "big", "error"),
        step("r2", 1, "model", "big", "invalid", prompt=500, completion=20),
    ),
)


class TestRedact(unittest.TestCase):
    def test_replaces_a_secret_value(self):
        self.assertEqual(
            redact({"api_key": "sk-live-1234", "q": "widgets"}, SECRETS),
            {"api_key": REDACTED, "q": "widgets"},
        )

    def test_matches_keys_case_insensitively(self):
        self.assertEqual(redact({"API_Key": "sk-live"}, SECRETS), {"API_Key": REDACTED})

    def test_reaches_into_nested_dicts(self):
        payload = {"request": {"headers": {"authorization": "Bearer x"}, "path": "/v1"}}
        self.assertEqual(
            redact(payload, SECRETS),
            {"request": {"headers": {"authorization": REDACTED}, "path": "/v1"}},
            "the interesting secrets are never at the top level",
        )

    def test_reaches_into_dicts_inside_lists(self):
        payload = {"users": [{"email": "a@example.com"}, {"email": "b@example.com"}]}
        self.assertEqual(
            redact(payload, SECRETS),
            {"users": [{"email": REDACTED}, {"email": REDACTED}]},
        )

    def test_does_not_mutate_the_input(self):
        payload = {"api_key": "sk-live-1234", "nested": {"email": "a@example.com"}}
        redact(payload, SECRETS)
        self.assertEqual(
            payload,
            {"api_key": "sk-live-1234", "nested": {"email": "a@example.com"}},
            "the stored record is the audit trail; redaction copies, it does not edit",
        )

    def test_an_empty_secret_set_changes_nothing(self):
        payload = {"api_key": "sk-live"}
        self.assertEqual(redact(payload, frozenset()), payload)


class TestClassifyFailure(unittest.TestCase):
    def test_a_successful_step_has_no_bucket(self):
        self.assertIsNone(classify_failure(step("r", 0, "model", "big", "ok")))

    def test_a_model_error_is_a_provider_error(self):
        self.assertEqual(
            classify_failure(step("r", 0, "model", "big", "error")), "provider_error"
        )

    def test_a_tool_error_is_a_tool_error(self):
        self.assertEqual(
            classify_failure(step("r", 0, "tool", "search", "error")), "tool_error"
        )

    def test_an_invalid_model_step_is_a_malformed_tool_call(self):
        self.assertEqual(
            classify_failure(step("r", 0, "model", "big", "invalid")),
            "malformed_tool_call",
            "a provider being down and a model emitting bad JSON have nothing in "
            "common except that both look like a failure",
        )

    def test_an_invalid_validate_step_is_a_rejected_output(self):
        self.assertEqual(
            classify_failure(step("r", 0, "validate", "schema", "invalid")),
            "output_rejected",
        )

    def test_aborted_is_budget_exhaustion_whatever_the_kind(self):
        self.assertEqual(
            classify_failure(step("r", 0, "tool", "search", "aborted")),
            "budget_exhausted",
        )

    def test_an_unanticipated_combination_gets_its_own_bucket(self):
        self.assertEqual(
            classify_failure(step("r", 0, "cache", "redis", "error")),
            "unclassified",
            "a failure nobody has a name for is the one worth seeing, so it needs "
            "a bucket rather than a silent drop",
        )


class TestCostOf(unittest.TestCase):
    def test_prices_the_model_steps(self):
        self.assertAlmostEqual(cost_of(COMPLETED, PRICES), 0.048)

    def test_tool_steps_are_free(self):
        only_tools = RunRecord(
            run_id="r3",
            task="t",
            status="completed",
            steps=(step("r3", 0, "tool", "search", "ok"),),
        )
        self.assertEqual(cost_of(only_tools, PRICES), 0.0)

    def test_a_failed_call_still_costs_what_it_recorded(self):
        self.assertAlmostEqual(
            cost_of(BROKEN, PRICES),
            0.0056,
            msg="the call that produced 20 useless tokens was still billed for them",
        )

    def test_an_unpriced_model_raises(self):
        with self.assertRaises(UnknownPrice):
            cost_of(COMPLETED, {"small": (0.001, 0.002)})

    def test_the_price_table_is_an_argument(self):
        cheaper = {"big": (0.001, 0.003)}
        self.assertAlmostEqual(
            cost_of(COMPLETED, cheaper),
            0.0048,
            msg="prices move, so nothing here may hardcode one",
        )


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.add(COMPLETED)
        self.ledger.add(BROKEN)

    def test_a_run_comes_back_by_id(self):
        self.assertEqual(self.ledger.run("r1").task, "triage")

    def test_an_unknown_run_id_raises(self):
        with self.assertRaises(KeyError):
            self.ledger.run("nope")

    def test_the_same_run_cannot_be_added_twice(self):
        with self.assertRaises(LedgerError):
            self.ledger.add(COMPLETED)

    def test_the_trace_is_redacted(self):
        ledger = Ledger()
        ledger.add(
            RunRecord(
                run_id="r9",
                task="t",
                status="completed",
                steps=(step("r9", 0, "tool", "lookup", "ok", payload={"email": "a@b.c"}),),
            )
        )
        self.assertEqual(ledger.trace("r9", secret_keys=SECRETS)[0].payload, {"email": REDACTED})

    def test_the_trace_leaves_the_stored_record_alone(self):
        ledger = Ledger()
        payload = {"email": "a@b.c"}
        ledger.add(
            RunRecord(
                run_id="r9",
                task="t",
                status="completed",
                steps=(step("r9", 0, "tool", "lookup", "ok", payload=payload),),
            )
        )
        ledger.trace("r9", secret_keys=SECRETS)
        self.assertEqual(ledger.run("r9").steps[0].payload, {"email": "a@b.c"})

    def test_the_trace_keeps_the_steps_in_order(self):
        traced = self.ledger.trace("r1", secret_keys=SECRETS)
        self.assertEqual([s.index for s in traced], [0, 1, 2])

    def test_failure_counts_across_every_run(self):
        self.assertEqual(
            self.ledger.failure_counts(),
            {"malformed_tool_call": 1, "provider_error": 1},
            "counted per bucket and sorted, so two summaries diff cleanly",
        )

    def test_failure_counts_leaves_out_empty_buckets(self):
        self.assertNotIn("tool_error", self.ledger.failure_counts())

    def test_the_summary_counts_runs_and_completions(self):
        summary = self.ledger.summary(PRICES)
        self.assertEqual((summary.runs, summary.completed), (2, 1))

    def test_the_summary_charges_failed_runs_too(self):
        summary = self.ledger.summary(PRICES)
        self.assertAlmostEqual(
            summary.total_cost,
            0.0536,
            msg="a run that produced nothing still consumed tokens",
        )

    def test_cost_per_completed_task_divides_by_completions(self):
        summary = self.ledger.summary(PRICES)
        self.assertAlmostEqual(
            summary.cost_per_completed_task,
            0.0536,
            msg="one task completed, and it carries the cost of the one that did not",
        )

    def test_cost_per_completed_task_is_unbounded_when_nothing_completes(self):
        ledger = Ledger()
        ledger.add(BROKEN)
        self.assertEqual(
            ledger.summary(PRICES).cost_per_completed_task,
            math.inf,
            "money spent and nothing shipped is not a cost of zero",
        )

    def test_an_empty_ledger_summarises_to_zero(self):
        summary = Ledger().summary(PRICES)
        self.assertEqual((summary.runs, summary.total_cost), (0, 0.0))
        self.assertEqual(summary.cost_per_completed_task, 0.0)

    def test_mean_steps_per_completed_run(self):
        self.assertAlmostEqual(
            self.ledger.summary(PRICES).mean_steps_per_completed,
            3.0,
            msg="the failed run's two steps are not part of a completed task's cost "
            "in steps",
        )

    def test_mean_duration_comes_from_the_records(self):
        self.assertAlmostEqual(self.ledger.summary(PRICES).mean_duration_ms, 1200.0)

    def test_a_long_run_is_flagged(self):
        summary = self.ledger.summary(PRICES, step_threshold=2)
        self.assertEqual(
            summary.over_budget,
            ("r1",),
            "strictly more than the threshold, and it is a smell rather than an "
            "error: this is the run to read first",
        )

    def test_nothing_is_flagged_under_the_default_threshold(self):
        self.assertEqual(self.ledger.summary(PRICES).over_budget, ())

    def test_the_summary_carries_the_failure_counts(self):
        self.assertEqual(
            self.ledger.summary(PRICES).failures, self.ledger.failure_counts()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
