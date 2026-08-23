"""
Tests for: chain of verification.

Run with `python3 test.py`.
"""

from __future__ import annotations

import json
import unittest

from mockllm import MockClient, text

from solution import decompose, question_for, reconcile, run_verification, verify


class TestDecompose(unittest.TestCase):
    def test_splits_on_sentences(self):
        claims = decompose("The model shipped in March. The price was forty pounds.")
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["text"], "The model shipped in March")

    def test_splits_a_conjunction_into_two_claims(self):
        claims = decompose("The model shipped in March and sold forty thousand units.")
        self.assertEqual(
            len(claims),
            2,
            "one verdict on a joined sentence is a single answer to something "
            "that could be half right",
        )

    def test_drops_a_fragment_too_short_to_be_a_claim(self):
        claims = decompose("Yes. The model shipped in March.")
        self.assertEqual([c["text"] for c in claims], ["The model shipped in March"])

    def test_marks_a_judgement_as_not_checkable(self):
        claims = decompose("The results are a significant improvement.")
        self.assertFalse(
            claims[0]["checkable"],
            "running an opinion through a fact check produces a "
            "confident-sounding verdict on a matter of taste",
        )

    def test_keeps_a_judgement_rather_than_dropping_it(self):
        claims = decompose("The results are a significant improvement.")
        self.assertEqual(len(claims), 1, "it still belongs in the final answer")

    def test_marks_a_fact_as_checkable(self):
        claims = decompose("The model shipped in March.")
        self.assertTrue(claims[0]["checkable"])

    def test_strips_trailing_full_stops(self):
        claims = decompose("The model shipped in March.")
        self.assertFalse(claims[0]["text"].endswith("."))

    def test_empty_input_gives_nothing(self):
        self.assertEqual(decompose(""), [])


class TestVerifyIndependence(unittest.TestCase):
    def test_a_verification_call_carries_its_claim_and_no_others(self):
        # This is the whole pattern, and the property is precise. The claim
        # under test HAS to be in the prompt, or there is no question to ask.
        # What must not be there is the rest of the draft: the other claims and
        # the reasoning that produced them, which are what would make the check
        # agree with the answer it is checking.
        draft = "The model shipped in March. The model sold forty thousand units."
        client = MockClient([text("March."), text("Forty thousand.")])
        run_verification(client, draft)

        first = json.dumps(client.requests[0]["messages"])
        self.assertIn("March", first, "the claim under test has to be asked about")
        self.assertNotIn(
            "forty thousand",
            first,
            "the second claim leaked into the first claim's verification, so "
            "the check is reading the draft it is checking",
        )

        second = json.dumps(client.requests[1]["messages"])
        self.assertIn("forty thousand", second)
        self.assertNotIn("March", second)

    def test_sends_only_the_question(self):
        client = MockClient([text("answer")])
        verify(client, "What is true about: the sky is blue?")
        messages = client.requests[-1]["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[1]["content"], "What is true about: the sky is blue?")

    def test_calls_the_model_once(self):
        client = MockClient([text("a")])
        verify(client, "q")
        self.assertEqual(client.call_count, 1)

    def test_question_for_mentions_the_claim(self):
        self.assertIn("the sky is blue", question_for("the sky is blue"))


class TestReconcile(unittest.TestCase):
    def test_agreement_is_supported(self):
        self.assertEqual(
            reconcile("shipped in March", "It shipped in March of that year."),
            "supported",
        )

    def test_disagreement_is_contradicted(self):
        self.assertEqual(
            reconcile("shipped in March", "It shipped in November."), "contradicted"
        )

    def test_not_knowing_is_unsupported_not_contradicted(self):
        self.assertEqual(
            reconcile("shipped in March", "Unknown, I have no record of that."),
            "unsupported",
            "the claim may be perfectly true and simply outside what the "
            "verification could reach",
        )

    def test_the_unknown_check_runs_first(self):
        # An answer that both disagrees and admits ignorance is unsupported.
        self.assertEqual(
            reconcile("shipped in March", "I cannot say; possibly November."),
            "unsupported",
        )

    def test_is_case_insensitive(self):
        self.assertEqual(reconcile("shipped in MARCH", "it shipped in march"), "supported")

    def test_ignores_short_words(self):
        self.assertEqual(reconcile("it was in March", "March, yes"), "supported")


class TestRunVerification(unittest.TestCase):
    def test_keeps_a_supported_claim(self):
        client = MockClient([text("The model shipped in March of that year.")])
        result = run_verification(client, "The model shipped in March.")
        self.assertEqual(result["counts"]["supported"], 1)
        self.assertIn("shipped in March", result["final"])

    def test_drops_a_contradicted_claim(self):
        client = MockClient([text("It shipped in November.")])
        result = run_verification(client, "The model shipped in March.")
        self.assertEqual(result["counts"]["contradicted"], 1)
        self.assertEqual(result["final"], "")

    def test_marks_an_unsupported_claim_rather_than_deleting_it(self):
        client = MockClient([text("Unknown.")])
        result = run_verification(client, "The model shipped in March.")
        self.assertIn(
            "[unverified]",
            result["final"],
            "deleting it silently loses good content; keeping it silently keeps "
            "a claim you failed to check",
        )

    def test_a_judgement_costs_no_model_call(self):
        client = MockClient([])
        result = run_verification(client, "The results are a significant improvement.")
        self.assertEqual(client.call_count, 0)
        self.assertEqual(result["counts"]["skipped"], 1)

    def test_a_judgement_survives_into_the_final_answer(self):
        client = MockClient([])
        result = run_verification(client, "The results are a significant improvement.")
        self.assertIn("significant improvement", result["final"])

    def test_one_call_per_checkable_claim(self):
        client = MockClient([text("March."), text("Forty thousand units.")])
        run_verification(client, "It shipped in March. It sold forty thousand units.")
        self.assertEqual(client.call_count, 2)

    def test_counts_add_up_to_the_claims(self):
        client = MockClient([text("The model shipped in March."), text("Unknown.")])
        result = run_verification(
            client, "The model shipped in March. The price was forty pounds."
        )
        self.assertEqual(sum(result["counts"].values()), len(result["claims"]))

    def test_every_claim_carries_a_verdict(self):
        client = MockClient([text("March.")], strict=False)
        result = run_verification(
            client, "The model shipped in March. The results are impressive."
        )
        self.assertTrue(all("verdict" in c for c in result["claims"]))

    def test_a_mixed_draft_keeps_only_what_survived(self):
        client = MockClient(
            [text("The model shipped in March."), text("The model sold four units.")]
        )
        result = run_verification(
            client, "The model shipped in March. The model sold forty thousand units."
        )
        self.assertIn("shipped in March", result["final"])
        self.assertNotIn("forty thousand", result["final"])

    def test_an_empty_draft_produces_an_empty_answer(self):
        client = MockClient([])
        result = run_verification(client, "")
        self.assertEqual(result["final"], "")
        self.assertEqual(result["claims"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
