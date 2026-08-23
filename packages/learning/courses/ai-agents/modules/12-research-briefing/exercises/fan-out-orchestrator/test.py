"""
Tests for: fan out, and what it costs.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, Usage, tool_call

from solution import (
    Budget,
    BudgetExceeded,
    Doc,
    Note,
    Research,
    WorkerOutput,
    make_search,
    orchestrate,
    plan,
    run_worker,
)

# The corpus lives here, not in solution.py. A worker that only ever sees the
# documents its search returned is the property these tests are checking, so the
# fixture has to be handed in from outside.
CORPUS = [
    Doc(
        "d-solar",
        "Solar module prices",
        "Solar module prices fell 41 percent last year as polysilicon supply "
        "expanded. Installers passed roughly half of that decline on to customers.",
    ),
    Doc(
        "d-storage",
        "Grid battery storage",
        "Grid battery storage additions doubled, and four hour lithium systems now "
        "clear the capacity auctions in three markets.",
    ),
    Doc(
        "d-queue",
        "Interconnection queue",
        "The interconnection queue holds 2.6 terawatts of projects, and the median "
        "wait from application to agreement is five years.",
    ),
    Doc(
        "d-wind",
        "Offshore wind costs",
        "Offshore wind costs rose for the third year, driven by vessel day rates "
        "and higher financing costs.",
    ),
    Doc(
        "d-jobs",
        "Sector employment",
        "Sector employment grew 8 percent, with most of the new roles in "
        "installation rather than manufacturing.",
    ),
]

SOLAR = "how did solar module prices move"
STORAGE = "battery storage additions"
QUESTION = "What happened to renewable project economics last year?"


def notes_step(*pairs):
    """A scripted record_notes call from (doc_id, quote) pairs."""
    return tool_call(
        "record_notes",
        {"notes": [{"doc_id": doc_id, "quote": quote} for doc_id, quote in pairs]},
    )


def sent_text(request):
    """Everything the loop put in one request's messages, as one string."""
    return "\n".join(str(message.get("content") or "") for message in request["messages"])


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.search = make_search(CORPUS)

    def test_search_returns_k_documents(self):
        self.assertEqual(len(self.search(SOLAR, 2)), 2)
        self.assertEqual(len(self.search(SOLAR, 4)), 4)

    def test_search_ranks_the_matching_document_first(self):
        self.assertEqual(
            self.search(SOLAR, 1)[0].id,
            "d-solar",
            "the top result should be the document whose words overlap the query",
        )

    def test_search_is_deterministic(self):
        first = [doc.id for doc in self.search(STORAGE, 3)]
        second = [doc.id for doc in self.search(STORAGE, 3)]
        self.assertEqual(first, second, "two identical searches must rank identically")

    def test_search_breaks_ties_by_doc_id(self):
        twins = [
            Doc("d-zeta", "Twin", "identical wording in both documents"),
            Doc("d-alpha", "Twin", "identical wording in both documents"),
        ]
        ranked = make_search(twins)("identical wording", 2)
        self.assertEqual(
            [doc.id for doc in ranked],
            ["d-alpha", "d-zeta"],
            "documents scoring the same must come back in doc id order",
        )


class TestPlan(unittest.TestCase):
    def test_plan_returns_the_scripted_sub_queries(self):
        client = MockClient([tool_call("plan", {"sub_queries": [SOLAR, STORAGE]})])
        self.assertEqual(plan(client, QUESTION), [SOLAR, STORAGE])

    def test_plan_truncates_to_the_cap(self):
        client = MockClient([tool_call("plan", {"sub_queries": ["a", "b", "c", "d", "e"]})])
        self.assertEqual(
            plan(client, QUESTION, max_sub_queries=3),
            ["a", "b", "c"],
            "max_sub_queries is a hard cap, because every extra one is a model call",
        )

    def test_plan_removes_duplicates_and_keeps_order(self):
        client = MockClient([tool_call("plan", {"sub_queries": ["b", "a", "b", "c"]})])
        self.assertEqual(plan(client, QUESTION), ["b", "a", "c"])

    def test_plan_strips_blanks(self):
        client = MockClient([tool_call("plan", {"sub_queries": ["  ", "a  ", ""]})])
        self.assertEqual(plan(client, QUESTION), ["a"])

    def test_plan_falls_back_to_the_question(self):
        client = MockClient([tool_call("plan", {"sub_queries": []})])
        self.assertEqual(
            plan(client, QUESTION),
            [QUESTION],
            "an empty plan should still run one worker on the original question",
        )

    def test_plan_charges_the_budget_when_given_one(self):
        client = MockClient([tool_call("plan", {"sub_queries": ["a"]})])
        budget = Budget(limit=10_000)
        plan(client, QUESTION, budget=budget)
        self.assertGreater(budget.spent, 0, "the planning call is a model call and costs")
        self.assertEqual(list(budget.by_stage), ["plan"])


class TestBudget(unittest.TestCase):
    def test_charge_adds_to_the_total_and_the_stage(self):
        budget = Budget(limit=1000)
        budget.charge("plan", Usage(prompt_tokens=40, completion_tokens=10))
        budget.charge("worker", Usage(prompt_tokens=90, completion_tokens=10))
        budget.charge("worker", Usage(prompt_tokens=90, completion_tokens=10))
        self.assertEqual(budget.spent, 250)
        self.assertEqual(budget.by_stage, {"plan": 50, "worker": 200})

    def test_charge_allows_spending_exactly_the_limit(self):
        budget = Budget(limit=50)
        budget.charge("plan", Usage(prompt_tokens=40, completion_tokens=10))
        self.assertEqual(budget.spent, 50, "the limit is a ceiling, not a wall one short")

    def test_charge_raises_when_the_limit_is_passed(self):
        budget = Budget(limit=50)
        with self.assertRaises(BudgetExceeded):
            budget.charge("worker", Usage(prompt_tokens=60, completion_tokens=10))
        self.assertEqual(
            budget.spent, 70, "record the spend that tripped the limit, then raise"
        )


class TestWorker(unittest.TestCase):
    def setUp(self):
        self.search = make_search(CORPUS)

    def test_worker_sees_only_its_own_documents(self):
        mine = self.search(SOLAR, 2)
        theirs = self.search(STORAGE, 2)
        self.assertFalse(
            {doc.id for doc in mine} & {doc.id for doc in theirs},
            "fixture check: these two sub queries should retrieve different documents",
        )

        client = MockClient([notes_step((mine[0].id, "prices fell 41 percent"))])
        run_worker(client, self.search, SOLAR, Budget(limit=10_000), "w1")

        blob = sent_text(client.requests[0])
        for doc in mine:
            self.assertIn(doc.text, blob, "the worker must be given its own documents")
        for doc in theirs:
            self.assertNotIn(
                doc.text,
                blob,
                "a worker must never see another worker's documents. Isolation is the "
                "whole reason fanning out is worth its cost",
            )

    def test_worker_message_carries_its_sub_query(self):
        client = MockClient([notes_step(("d-solar", "prices fell"))])
        run_worker(client, self.search, SOLAR, Budget(limit=10_000), "w1")
        self.assertIn(SOLAR, sent_text(client.requests[0]))

    def test_worker_records_the_worker_name_and_sub_query(self):
        client = MockClient([notes_step(("d-solar", "prices fell 41 percent"))])
        output = run_worker(client, self.search, SOLAR, Budget(limit=10_000), "w7")
        self.assertIsInstance(output, WorkerOutput)
        self.assertEqual(len(output.notes), 1)
        self.assertEqual(output.notes[0].worker, "w7")
        self.assertEqual(output.notes[0].sub_query, SOLAR)
        self.assertEqual(output.notes[0].quote, "prices fell 41 percent")
        self.assertEqual(output.dropped, 0, "nothing was fabricated, so nothing was dropped")

    def test_worker_drops_a_note_citing_an_unseen_document(self):
        mine = {doc.id for doc in self.search(SOLAR, 2)}
        unseen = next(doc.id for doc in CORPUS if doc.id not in mine)

        client = MockClient(
            [notes_step(("d-solar", "first"), (unseen, "invented"), ("d-solar", "second"))]
        )
        output = run_worker(client, self.search, SOLAR, Budget(limit=10_000), "w1")

        self.assertEqual(
            [note.quote for note in output.notes],
            ["first", "second"],
            "a note citing a document the worker never received is fabricated, and the "
            "surviving notes keep their order",
        )

    def test_worker_counts_what_it_dropped(self):
        mine = {doc.id for doc in self.search(SOLAR, 2)}
        unseen = next(doc.id for doc in CORPUS if doc.id not in mine)

        client = MockClient(
            [notes_step(("d-solar", "kept"), (unseen, "invented"), (unseen, "also invented"))]
        )
        output = run_worker(client, self.search, SOLAR, Budget(limit=10_000), "w1")

        self.assertEqual(
            output.dropped,
            2,
            "this function is the last place that knows a note was fabricated. Discard "
            "the count with the note and no eval can ever report a fabrication rate",
        )

    def test_worker_charges_the_worker_stage(self):
        client = MockClient([notes_step(("d-solar", "prices fell"))])
        budget = Budget(limit=10_000)
        run_worker(client, self.search, SOLAR, budget, "w1")
        self.assertEqual(list(budget.by_stage), ["worker"])
        self.assertGreater(budget.by_stage["worker"], 0)


class TestOrchestrate(unittest.TestCase):
    def setUp(self):
        self.search = make_search(CORPUS)

    def _client(self, sub_queries, *note_steps):
        return MockClient([tool_call("plan", {"sub_queries": sub_queries})] + list(note_steps))

    def test_orchestrate_returns_the_plan_and_the_notes(self):
        client = self._client(
            [SOLAR, STORAGE],
            notes_step(("d-solar", "prices fell 41 percent")),
            notes_step(("d-storage", "storage additions doubled")),
        )
        research = orchestrate(client, self.search, CORPUS, QUESTION, Budget(limit=10_000))

        self.assertIsInstance(research, Research)
        self.assertEqual(research.sub_queries, [SOLAR, STORAGE])
        self.assertEqual(len(research.notes), 2)
        self.assertEqual([note.worker for note in research.notes], ["w1", "w2"])
        self.assertEqual(client.call_count, 3, "one plan call plus one call per worker")

    def test_orchestrate_records_the_corpus_it_read(self):
        client = self._client([SOLAR], notes_step(("d-solar", "prices fell 41 percent")))
        research = orchestrate(client, self.search, CORPUS, QUESTION, Budget(limit=10_000))

        self.assertEqual(
            [doc.id for doc in research.corpus],
            [doc.id for doc in CORPUS],
            "the run has to carry the documents it read. A note holds a doc id and "
            "nothing else, so a Research without a corpus hands the next stage a "
            "citation it cannot turn into a title",
        )

    def test_orchestrate_sums_what_the_workers_dropped(self):
        client = self._client(
            [SOLAR, STORAGE],
            notes_step(("d-solar", "kept"), ("d-jobs", "invented")),
            notes_step(("d-storage", "kept"), ("d-wind", "invented")),
        )
        research = orchestrate(client, self.search, CORPUS, QUESTION, Budget(limit=10_000))

        self.assertEqual(len(research.notes), 2)
        self.assertEqual(
            research.dropped,
            2,
            "one fabricated note per worker, and the run reports both. This is the "
            "fabrication rate an eval reads later",
        )

    def test_orchestrate_separates_plan_and_worker_spend(self):
        client = self._client(
            [SOLAR, STORAGE],
            notes_step(("d-solar", "a")),
            notes_step(("d-storage", "b")),
        )
        budget = Budget(limit=10_000)
        orchestrate(client, self.search, CORPUS, QUESTION, budget)

        self.assertEqual(sorted(budget.by_stage), ["plan", "worker"])
        self.assertEqual(
            budget.spent,
            sum(budget.by_stage.values()),
            "the total and the per stage figures must describe the same run",
        )

    def _spend_through_the_first_worker(self):
        """Measure a real plan plus one worker, so the limit below is not a guess."""
        client = self._client([SOLAR, STORAGE], notes_step(("d-solar", "measuring")))
        budget = Budget(limit=10_000_000)
        sub_queries = plan(client, QUESTION, budget=budget)
        run_worker(client, self.search, sub_queries[0], budget, "w1")
        return budget.spent

    def test_orchestrate_keeps_the_notes_when_the_budget_runs_out(self):
        client = self._client(
            [SOLAR, STORAGE],
            notes_step(("d-solar", "prices fell 41 percent")),
            notes_step(("d-storage", "storage additions doubled")),
        )
        # Exactly enough for the plan and the first worker, and not a token more.
        budget = Budget(limit=self._spend_through_the_first_worker())
        with self.assertRaises(BudgetExceeded) as caught:
            orchestrate(client, self.search, CORPUS, QUESTION, budget)

        self.assertTrue(
            caught.exception.notes,
            "work already paid for should come back attached to the exception rather "
            "than being thrown away with it",
        )
        self.assertEqual(caught.exception.notes[0].quote, "prices fell 41 percent")

    def test_fanning_out_costs_more_than_one_query(self):
        wide = self._client(
            [SOLAR, STORAGE, "what slows projects down", "offshore wind cost drivers"],
            notes_step(("d-solar", "a")),
            notes_step(("d-storage", "b")),
            notes_step(("d-queue", "c")),
            notes_step(("d-wind", "d")),
        )
        wide_budget = Budget(limit=100_000)
        orchestrate(wide, self.search, CORPUS, QUESTION, wide_budget)

        narrow = self._client([SOLAR], notes_step(("d-solar", "a")))
        narrow_budget = Budget(limit=100_000)
        orchestrate(narrow, self.search, CORPUS, QUESTION, narrow_budget)

        self.assertGreater(
            wide_budget.spent,
            narrow_budget.spent,
            "four workers cost more than one. The number is not the point; noticing "
            "that coverage is bought with tokens is",
        )

    def test_orchestrate_respects_the_sub_query_cap(self):
        client = self._client(
            ["a", "b", "c", "d", "e"],
            notes_step(("d-solar", "one")),
            notes_step(("d-solar", "two")),
        )
        research = orchestrate(
            client, self.search, CORPUS, QUESTION, Budget(limit=100_000), max_sub_queries=2
        )
        self.assertEqual(len(research.sub_queries), 2)
        self.assertEqual(client.call_count, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
