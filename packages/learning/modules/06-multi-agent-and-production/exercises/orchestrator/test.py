"""
Tests for: an orchestrator and its workers.

Run with `python3 test.py`.
"""

from __future__ import annotations

import json
import unittest

from mockllm import MockClient, error, text

from solution import (
    Orchestrator,
    PlanError,
    Subtask,
    WorkerResult,
    aggregate,
    goal_fingerprint,
    parse_plan,
    plan_problems,
    run_worker,
)

WORKER_SYSTEM = "Answer the goal from the sources you have. JSON only."


def entry(id, goal, key, depends_on=None):
    payload = {"id": id, "goal": goal, "key": key}
    if depends_on is not None:
        payload["depends_on"] = depends_on
    return payload


def plan_reply(*entries):
    return text(json.dumps({"subtasks": list(entries)}))


def worker_reply(key, value, confidence=0.9, evidence="doc-1"):
    return text(
        json.dumps(
            {"key": key, "value": value, "confidence": confidence, "evidence": evidence}
        )
    )


def ok(subtask_id, key, value, confidence):
    return WorkerResult(
        subtask_id=subtask_id,
        status="ok",
        key=key,
        value=value,
        confidence=confidence,
        evidence="doc-1",
    )


PRICE = Subtask(id="t1", goal="find the list price on the pricing page", key="price")
SEATS = Subtask(id="t2", goal="find the seat minimum in the contract", key="seats")


class TestParsePlan(unittest.TestCase):
    def test_parses_the_subtasks_in_order(self):
        subtasks = parse_plan(
            json.dumps(
                {"subtasks": [entry("t1", "goal one", "price"), entry("t2", "goal two", "seats")]}
            )
        )
        self.assertEqual([t.id for t in subtasks], ["t1", "t2"])
        self.assertEqual(subtasks[0].key, "price")

    def test_depends_on_defaults_to_an_empty_tuple(self):
        subtasks = parse_plan(json.dumps({"subtasks": [entry("t1", "g", "k")]}))
        self.assertEqual(subtasks[0].depends_on, ())

    def test_depends_on_becomes_a_tuple(self):
        subtasks = parse_plan(
            json.dumps({"subtasks": [entry("t2", "g", "k", depends_on=["t1"])]})
        )
        self.assertEqual(subtasks[0].depends_on, ("t1",))

    def test_rejects_prose(self):
        with self.assertRaises(PlanError):
            parse_plan("First I would look up the price, then the seat count.")

    def test_rejects_a_reply_with_no_subtasks_list(self):
        with self.assertRaises(PlanError):
            parse_plan(json.dumps({"steps": []}))

    def test_rejects_a_blank_goal(self):
        with self.assertRaises(PlanError):
            parse_plan(json.dumps({"subtasks": [entry("t1", "   ", "price")]}))

    def test_rejects_a_missing_key(self):
        with self.assertRaises(PlanError):
            parse_plan(json.dumps({"subtasks": [{"id": "t1", "goal": "g"}]}))

    def test_rejects_a_depends_on_that_is_not_a_list_of_ids(self):
        with self.assertRaises(PlanError):
            parse_plan(json.dumps({"subtasks": [entry("t1", "g", "k", depends_on="t0")]}))


class TestPlanProblems(unittest.TestCase):
    def test_a_runnable_plan_has_no_problems(self):
        self.assertEqual(plan_problems([PRICE, SEATS], max_workers=4), [])

    def test_an_empty_plan_is_a_problem(self):
        self.assertEqual(
            len(plan_problems([], max_workers=4)),
            1,
            "an empty plan is one problem: fanning out to zero workers would "
            "otherwise produce a confident empty report",
        )

    def test_duplicate_ids_are_a_problem(self):
        problems = plan_problems([PRICE, PRICE], max_workers=4)
        self.assertTrue(
            any("t1" in problem for problem in problems),
            "the sentence has to name the repeated id. Word it how you like, but "
            f"a reader must not have to go back to the plan. Got: {problems}",
        )

    def test_goals_that_differ_only_in_word_order_overlap(self):
        twin = Subtask(id="t9", goal="price list the on find page the pricing", key="price")
        self.assertEqual(
            goal_fingerprint(PRICE.goal),
            goal_fingerprint(twin.goal),
            "the fingerprint drops word order on purpose",
        )
        problems = plan_problems([PRICE, twin], max_workers=4)
        self.assertTrue(
            any("t1" in problem and "t9" in problem for problem in problems),
            "same tokens, same work, so this is a problem, and its sentence has "
            f"to name both subtask ids. Got: {problems}",
        )

    def test_a_dependency_is_a_problem(self):
        dependent = Subtask(
            id="t2", goal="compare it to the list price", key="gap", depends_on=("t1",)
        )
        problems = plan_problems([PRICE, dependent], max_workers=4)
        self.assertTrue(
            any("t2" in problem and "t1" in problem for problem in problems),
            "a subtask needing another's output cannot run in the same fan out, "
            "and its sentence has to name the dependent id and what it depends "
            f"on. Got: {problems}",
        )

    def test_more_subtasks_than_workers_is_a_problem(self):
        problems = plan_problems([PRICE, SEATS], max_workers=1)
        self.assertEqual(len(problems), 1)
        self.assertTrue(
            "2" in problems[0] and "1" in problems[0],
            "the sentence has to name both numbers, the subtask count and the "
            f"cap it exceeded. Got: {problems[0]!r}",
        )

    def test_every_problem_is_reported_at_once(self):
        dependent = Subtask(id="t1", goal="another goal entirely", key="gap", depends_on=("t0",))
        problems = plan_problems([PRICE, dependent], max_workers=4)
        self.assertEqual(
            len(problems),
            2,
            "a duplicate id and a dependency are two problems, and fixing them one "
            "call at a time is how a planning loop gets expensive",
        )

    def test_problems_come_back_sorted(self):
        problems = plan_problems([PRICE, PRICE, SEATS], max_workers=1)
        self.assertEqual(problems, sorted(problems))


class TestRunWorker(unittest.TestCase):
    def test_an_answered_subtask_is_ok(self):
        client = MockClient([worker_reply("price", "49", 0.8, "pricing-page")])
        result = run_worker(client, PRICE, system=WORKER_SYSTEM)
        self.assertEqual(result.status, "ok")
        self.assertEqual((result.key, result.value), ("price", "49"))
        self.assertEqual(result.evidence, "pricing-page")
        self.assertAlmostEqual(result.confidence, 0.8)

    def test_sends_the_system_prompt_and_the_goal_alone(self):
        client = MockClient([worker_reply("price", "49")])
        run_worker(client, PRICE, system=WORKER_SYSTEM)
        sent = client.requests[0]["messages"]
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["content"], WORKER_SYSTEM)
        self.assertEqual(sent[1]["content"], PRICE.goal)

    def test_a_worker_never_sees_another_subtask(self):
        client = MockClient([worker_reply("price", "49"), worker_reply("seats", "5")])
        run_worker(client, PRICE, system=WORKER_SYSTEM)
        run_worker(client, SEATS, system=WORKER_SYSTEM)
        first = json.dumps(client.requests[0]["messages"])
        self.assertNotIn(
            SEATS.goal,
            first,
            "isolation is the whole point of a worker: a prompt carrying every "
            "subtask buys you one wide question asked twice, at twice the price",
        )

    def test_a_provider_failure_does_not_raise(self):
        client = MockClient([error("service unavailable", 503)])
        result = run_worker(client, PRICE, system=WORKER_SYSTEM)
        self.assertEqual(result.status, "failed")
        self.assertNotEqual(result.note, "", "a failure with no note is not debuggable")

    def test_a_reply_that_is_not_json_fails(self):
        client = MockClient([text("The price is about fifty dollars I think.")])
        self.assertEqual(run_worker(client, PRICE, system=WORKER_SYSTEM).status, "failed")

    def test_answering_the_wrong_key_fails(self):
        client = MockClient([worker_reply("seats", "5")])
        result = run_worker(client, PRICE, system=WORKER_SYSTEM)
        self.assertEqual(
            result.status,
            "failed",
            "a structured result can be checked against the request that produced "
            "it, and this worker answered a different question",
        )
        self.assertTrue(
            "price" in result.note and "seats" in result.note,
            "the note has to carry both keys, the one answered and the one asked "
            f"for, or the reader cannot see the mismatch. Got: {result.note!r}",
        )

    def test_an_empty_value_is_unknown_not_failed(self):
        client = MockClient([worker_reply("price", "")])
        result = run_worker(client, PRICE, system=WORKER_SYSTEM)
        self.assertEqual(
            result.status,
            "unknown",
            "a worker that looked and found nothing did its job",
        )

    def test_a_value_with_no_evidence_is_unknown(self):
        client = MockClient([worker_reply("price", "49", 0.99, "")])
        self.assertEqual(
            run_worker(client, PRICE, system=WORKER_SYSTEM).status,
            "unknown",
            "confidence is not evidence",
        )


class TestAggregate(unittest.TestCase):
    def test_a_single_claim_settles(self):
        result = aggregate([ok("t1", "price", "49", 0.7)])
        self.assertEqual(result.findings, {"price": "49"})
        self.assertEqual(result.conflicts, ())

    def test_agreeing_claims_are_not_a_conflict(self):
        result = aggregate([ok("t1", "price", "49", 0.7), ok("t2", "price", "49", 0.4)])
        self.assertEqual(result.findings, {"price": "49"})
        self.assertEqual(result.conflicts, ())

    def test_a_disagreement_is_settled_by_confidence(self):
        result = aggregate([ok("t1", "price", "49", 0.9), ok("t2", "price", "59", 0.4)])
        self.assertEqual(result.findings, {"price": "49"})
        self.assertEqual(len(result.conflicts), 1)
        self.assertEqual(result.conflicts[0].winner, "49")

    def test_a_settled_conflict_is_still_reported(self):
        result = aggregate([ok("t1", "price", "49", 0.9), ok("t2", "price", "59", 0.4)])
        self.assertEqual(
            result.conflicts[0].claims,
            (("t1", "49", 0.9), ("t2", "59", 0.4)),
            "claims sort by confidence descending, then by subtask id",
        )
        self.assertEqual(result.unresolved, ())

    def test_a_tie_does_not_reach_findings(self):
        result = aggregate([ok("t1", "price", "49", 0.8), ok("t2", "price", "59", 0.8)])
        self.assertEqual(
            result.findings,
            {},
            "nothing separated the two, so this run did not establish the price. A "
            "guessed winner is indistinguishable from a real one downstream",
        )
        self.assertEqual(result.unresolved, ("price",))
        self.assertIsNone(result.conflicts[0].winner)

    def test_repeating_a_value_does_not_outvote_a_higher_confidence(self):
        result = aggregate(
            [
                ok("t1", "price", "59", 0.3),
                ok("t2", "price", "59", 0.3),
                ok("t3", "price", "49", 0.9),
            ]
        )
        self.assertEqual(
            result.findings,
            {"price": "49"},
            "three workers reading the same wrong source is one wrong source",
        )

    def test_other_keys_are_unaffected_by_a_conflict(self):
        result = aggregate(
            [ok("t1", "price", "49", 0.8), ok("t2", "price", "59", 0.8), ok("t3", "seats", "5", 0.6)]
        )
        self.assertEqual(result.findings, {"seats": "5"})

    def test_unknown_and_failed_are_collected_and_sorted(self):
        result = aggregate(
            [
                WorkerResult(subtask_id="t9", status="failed", note="boom"),
                WorkerResult(subtask_id="t3", status="unknown"),
                WorkerResult(subtask_id="t1", status="failed", note="boom"),
                ok("t2", "price", "49", 0.5),
            ]
        )
        self.assertEqual(result.failed, ("t1", "t9"))
        self.assertEqual(result.unknown, ("t3",))
        self.assertEqual(result.findings, {"price": "49"})

    def test_conflicts_are_sorted_by_key(self):
        result = aggregate(
            [
                ok("t1", "seats", "5", 0.9),
                ok("t2", "seats", "9", 0.1),
                ok("t3", "price", "49", 0.9),
                ok("t4", "price", "59", 0.1),
            ]
        )
        self.assertEqual([c.key for c in result.conflicts], ["price", "seats"])


class TestOrchestrator(unittest.TestCase):
    def orchestrator(self, *script, **kwargs):
        kwargs.setdefault("worker_system", WORKER_SYSTEM)
        return Orchestrator(MockClient(list(script)), **kwargs)

    def test_one_call_to_plan_and_one_per_worker(self):
        runner = self.orchestrator(
            plan_reply(entry("t1", "find the price", "price"), entry("t2", "find the seats", "seats")),
            worker_reply("price", "49"),
            worker_reply("seats", "5"),
        )
        report = runner.run("what does this cost")
        self.assertEqual(
            report.model_calls,
            3,
            "two workers is three conversations, and that is the number to look at "
            "before adding a third worker",
        )
        self.assertEqual(report.aggregate.findings, {"price": "49", "seats": "5"})

    def test_a_bad_plan_costs_exactly_one_call(self):
        client = MockClient(
            [plan_reply(entry("t1", "find the price", "price", depends_on=["t0"]))]
        )
        runner = Orchestrator(client, worker_system=WORKER_SYSTEM)
        with self.assertRaises(PlanError):
            runner.run("what does this cost")
        self.assertEqual(
            client.call_count,
            1,
            "the plan is checked before the fan out, so a pipeline dressed as a fan "
            "out costs one call and not one per subtask",
        )

    def test_the_plan_error_names_every_problem(self):
        runner = self.orchestrator(
            plan_reply(
                entry("t1", "find the price", "price"),
                entry("t1", "find the seat minimum", "seats"),
                entry("t3", "find the renewal date", "renewal"),
            ),
            max_workers=2,
        )
        with self.assertRaises(PlanError) as caught:
            runner.plan("what does this cost")
        message = str(caught.exception)
        self.assertIn("t1", message, "the duplicate id problem is in there")
        self.assertTrue(
            "3" in message and "2" in message,
            "and so is the cap problem, with both its numbers. Reporting one "
            f"problem at a time costs a planning call per problem. Got: {message!r}",
        )

    def test_workers_run_in_plan_order_with_their_own_goals(self):
        runner = self.orchestrator(
            plan_reply(entry("t1", "find the price", "price"), entry("t2", "find the seats", "seats")),
            worker_reply("price", "49"),
            worker_reply("seats", "5"),
        )
        report = runner.run("what does this cost")
        sent = [request["messages"][1]["content"] for request in runner.client.requests[1:]]
        self.assertEqual(sent, ["find the price", "find the seats"])
        self.assertEqual([r.subtask_id for r in report.results], ["t1", "t2"])

    def test_one_broken_worker_does_not_sink_the_run(self):
        runner = self.orchestrator(
            plan_reply(entry("t1", "find the price", "price"), entry("t2", "find the seats", "seats")),
            error("gateway timeout", 504),
            worker_reply("seats", "5"),
        )
        report = runner.run("what does this cost")
        self.assertEqual(report.aggregate.failed, ("t1",))
        self.assertEqual(
            report.aggregate.findings,
            {"seats": "5"},
            "the second worker's answer was paid for and is still good",
        )

    def test_the_report_carries_the_plan(self):
        runner = self.orchestrator(
            plan_reply(entry("t1", "find the price", "price")),
            worker_reply("price", "49"),
        )
        report = runner.run("what does this cost")
        self.assertEqual(report.question, "what does this cost")
        self.assertEqual([t.id for t in report.subtasks], ["t1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
