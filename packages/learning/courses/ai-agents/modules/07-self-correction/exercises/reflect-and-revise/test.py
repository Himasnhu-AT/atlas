"""
Tests for: reflection and its failure mode.

Run with `python3 test.py`.
"""

from __future__ import annotations

import json
import unittest

from mockllm import MockClient, text

from solution import critique, improvement, reflect, revise, score

CRITERIA = ["states its sources", "no unsupported numbers"]
RUBRIC = {"source:": 2, "approximately": 1}


class TestCritique(unittest.TestCase):
    def test_returns_one_finding_per_line(self):
        client = MockClient([text("no source given\nthe number 40000 is unsupported")])
        findings = critique(client, "draft", CRITERIA)
        self.assertEqual(findings, ["no source given", "the number 40000 is unsupported"])

    def test_none_means_no_findings(self):
        client = MockClient([text("NONE")])
        self.assertEqual(
            critique(client, "draft", CRITERIA),
            [],
            "the critique has to be able to return nothing, or a prompt asking "
            "what is wrong will find something wrong with a perfect answer",
        )

    def test_none_is_recognised_whatever_the_case_and_spacing(self):
        for reply in ["none", " None \n", "NONE"]:
            client = MockClient([text(reply)])
            self.assertEqual(critique(client, "d", CRITERIA), [])

    def test_drops_blank_lines(self):
        client = MockClient([text("first\n\n\nsecond\n")])
        self.assertEqual(critique(client, "d", CRITERIA), ["first", "second"])

    def test_sends_the_criteria_and_the_draft(self):
        client = MockClient([text("NONE")])
        critique(client, "THE DRAFT", CRITERIA)
        sent = json.dumps(client.requests[-1]["messages"])
        self.assertIn("THE DRAFT", sent)
        self.assertIn("states its sources", sent)

    def test_calls_the_model_once(self):
        client = MockClient([text("NONE")])
        critique(client, "d", CRITERIA)
        self.assertEqual(client.call_count, 1)


class TestRevise(unittest.TestCase):
    def test_returns_the_revision(self):
        client = MockClient([text("  a better draft  ")])
        self.assertEqual(revise(client, "draft", ["fix it"]), "a better draft")

    def test_sends_the_findings(self):
        client = MockClient([text("x")])
        revise(client, "draft", ["no source given"])
        self.assertIn("no source given", json.dumps(client.requests[-1]["messages"]))

    def test_tells_the_model_to_change_nothing_else(self):
        client = MockClient([text("x")])
        revise(client, "draft", ["f"])
        sent = json.dumps(client.requests[-1]["messages"]).lower()
        self.assertIn(
            "nothing else",
            sent,
            "without it, each pass makes small changes to please the critic and "
            "the answer drifts away from the question",
        )


class TestReflectLoop(unittest.TestCase):
    def test_stops_early_when_the_critique_is_clean(self):
        client = MockClient([text("NONE")])
        result = reflect(client, "already good", CRITERIA, max_passes=3)

        self.assertEqual(result["passes"], 0)
        self.assertEqual(result["stopped"], "clean")
        self.assertEqual(result["final"], "already good")
        self.assertEqual(client.call_count, 1, "no revision call when there is nothing to fix")

    def test_runs_a_pass_then_stops_clean(self):
        client = MockClient([text("no source given"), text("v2 source: docs"), text("NONE")])
        result = reflect(client, "v1", CRITERIA, max_passes=3)

        self.assertEqual(result["passes"], 1)
        self.assertEqual(result["stopped"], "clean")
        self.assertEqual(result["final"], "v2 source: docs")

    def test_respects_the_bound(self):
        # Always finds something, always revises. Without the bound this never
        # terminates.
        client = MockClient(
            [text("still wrong"), text("v2"), text("still wrong"), text("v3")]
        )
        result = reflect(client, "v1", CRITERIA, max_passes=2)

        self.assertEqual(result["passes"], 2)
        self.assertEqual(result["stopped"], "limit")
        self.assertEqual(result["final"], "v3")

    def test_never_calls_more_than_the_bound_allows(self):
        client = MockClient([text("f"), text("v2"), text("f"), text("v3")], strict=False)
        reflect(client, "v1", CRITERIA, max_passes=2)
        self.assertLessEqual(client.call_count, 4)

    def test_history_records_each_pass(self):
        client = MockClient([text("finding one"), text("v2"), text("NONE")])
        result = reflect(client, "v1", CRITERIA, max_passes=3)

        self.assertEqual(result["history"][0]["draft"], "v1")
        self.assertEqual(result["history"][0]["findings"], ["finding one"])
        self.assertEqual(result["history"][0]["revised"], "v2")

    def test_a_clean_first_critique_still_records_an_entry(self):
        client = MockClient([text("NONE")])
        result = reflect(client, "v1", CRITERIA)
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(result["history"][0]["revised"], "v1")


class TestScore(unittest.TestCase):
    def test_adds_up_matches(self):
        self.assertEqual(score("source: docs, approximately 40", RUBRIC), 3)

    def test_is_case_insensitive(self):
        self.assertEqual(score("SOURCE: docs", RUBRIC), 2)

    def test_counts_each_key_once(self):
        self.assertEqual(score("source: a source: b", RUBRIC), 2)

    def test_nothing_matching_is_zero(self):
        self.assertEqual(score("plain text", RUBRIC), 0)


class TestImprovement(unittest.TestCase):
    def test_reports_a_real_improvement(self):
        history = [{"draft": "v1", "findings": ["f"], "revised": "v2 source: docs"}]
        self.assertEqual(improvement(history, RUBRIC)[0]["verdict"], "better")

    def test_reports_a_regression(self):
        history = [{"draft": "v1 source: docs", "findings": ["f"], "revised": "v2"}]
        self.assertEqual(improvement(history, RUBRIC)[0]["verdict"], "worse")

    def test_a_rewrite_that_scores_the_same_is_unchanged(self):
        history = [{"draft": "the results are good", "findings": ["f"], "revised": "the results are strong"}]
        self.assertEqual(
            improvement(history, RUBRIC)[0]["verdict"],
            "unchanged",
            "the text moved and the score did not, which is the drift this "
            "harness exists to expose",
        )

    def test_numbers_each_pass(self):
        history = [
            {"draft": "a", "findings": ["f"], "revised": "b"},
            {"draft": "b", "findings": ["f"], "revised": "c"},
        ]
        self.assertEqual([e["pass"] for e in improvement(history, RUBRIC)], [1, 2])


class TestLaundering(unittest.TestCase):
    def test_reflection_fixes_the_form_and_leaves_the_error(self):
        # A factually wrong draft. The critique finds a real but cosmetic
        # problem, the revision fixes it, and the wrong fact survives into a
        # better-written answer that now carries evidence of review.
        wrong = "The 2019 model sold 40000 units."
        client = MockClient(
            [
                text("no source is given"),
                text("Source: internal report. The 2019 model sold 40000 units."),
                text("NONE"),
            ]
        )
        result = reflect(client, wrong, CRITERIA, max_passes=3)

        self.assertEqual(result["stopped"], "clean", "the loop was perfectly happy")
        self.assertIn(
            "40000",
            result["final"],
            "reflection improved the presentation and left the error, and made "
            "it more convincing on the way past",
        )

        scored = improvement(result["history"], RUBRIC)
        self.assertEqual(
            scored[0]["verdict"],
            "better",
            "and the rubric agrees it improved, which is exactly the trap",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
