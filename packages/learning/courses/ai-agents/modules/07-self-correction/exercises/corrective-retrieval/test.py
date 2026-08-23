"""
Tests for: retrieval that corrects itself.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    answer,
    filter_results,
    grade,
    needs_retrieval,
    retrieve,
    rewrite_query,
)

CORPUS = [
    "Error 402: payment method rejected. Ask the customer to update their card details.",
    "Refunds are issued to the original payment method within five working days.",
    "Our office hours are nine to five, Monday to Friday.",
    "The billing cycle runs monthly on the date of signup.",
]

# The corpus says "error 402"; users say "my card got declined". This mapping is
# the whole reason a second attempt is worth making.
VOCABULARY = {
    "what does error 402 mean": "error 402 payment method rejected",
    "card get declined": "error 402 payment method rejected",
}

USER_PHRASING = "What does error 402 mean?"
CORPUS_PHRASING = "error 402 payment method rejected"
OFF_TOPIC = "How do I train a neural network?"


class TestRetrieve(unittest.TestCase):
    def test_returns_k_chunks_best_first(self):
        results = retrieve(CORPUS_PHRASING, CORPUS, k=3)
        self.assertEqual(len(results), 3)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_finds_the_right_chunk_for_the_corpus_phrasing(self):
        results = retrieve(CORPUS_PHRASING, CORPUS, k=1)
        self.assertTrue(results[0]["text"].startswith("Error 402"))

    def test_returns_something_even_for_an_unanswerable_question(self):
        results = retrieve(OFF_TOPIC, CORPUS, k=3)
        self.assertEqual(
            len(results),
            3,
            "similarity search always returns something, with no signal that "
            "the corpus does not cover the question",
        )

    def test_an_empty_corpus_returns_nothing(self):
        self.assertEqual(retrieve("anything", [], k=3), [])

    def test_is_stable_across_runs(self):
        self.assertEqual(retrieve(OFF_TOPIC, CORPUS, k=3), retrieve(OFF_TOPIC, CORPUS, k=3))


class TestGrade(unittest.TestCase):
    def test_the_corpus_phrasing_is_relevant(self):
        # Measured: 0.620 against this chunk.
        self.assertEqual(grade(CORPUS_PHRASING, CORPUS[0]), "relevant")

    def test_the_users_phrasing_is_not(self):
        # Measured: 0.248. The chunk that answers the question does not score
        # like it, which is exactly why the rewrite exists.
        self.assertEqual(grade(USER_PHRASING, CORPUS[0]), "irrelevant")

    def test_an_unrelated_chunk_is_irrelevant(self):
        self.assertEqual(grade(CORPUS_PHRASING, CORPUS[2]), "irrelevant")

    def test_thresholds_are_honoured(self):
        self.assertEqual(grade(CORPUS_PHRASING, CORPUS[0], relevant=0.9), "ambiguous")
        self.assertEqual(
            grade(CORPUS_PHRASING, CORPUS[0], relevant=0.9, ambiguous=0.7), "irrelevant"
        )


class TestFilterResults(unittest.TestCase):
    def test_keeps_what_helps_and_drops_the_rest(self):
        results = retrieve(CORPUS_PHRASING, CORPUS, k=3)
        filtered = filter_results(CORPUS_PHRASING, results)

        self.assertGreaterEqual(len(filtered["kept"]), 1)
        self.assertGreaterEqual(filtered["dropped"], 1)
        self.assertFalse(filtered["all_irrelevant"])

    def test_every_kept_chunk_carries_its_grade(self):
        filtered = filter_results(CORPUS_PHRASING, retrieve(CORPUS_PHRASING, CORPUS))
        self.assertTrue(all("grade" in c for c in filtered["kept"]))

    def test_notices_when_nothing_survives(self):
        results = retrieve(OFF_TOPIC, CORPUS, k=3)
        filtered = filter_results(OFF_TOPIC, results)
        self.assertTrue(
            filtered["all_irrelevant"],
            "this is the pipeline discovering its corpus does not cover the "
            "question, which the plain version could never find out",
        )

    def test_empty_results_are_not_all_irrelevant(self):
        filtered = filter_results("anything", [])
        self.assertFalse(
            filtered["all_irrelevant"],
            "nothing was retrieved, which is a different fact from everything "
            "retrieved being useless",
        )


class TestRewriteQuery(unittest.TestCase):
    def test_says_the_question_the_way_the_documents_do(self):
        rewritten = rewrite_query(USER_PHRASING, VOCABULARY)
        self.assertIn("payment method rejected", rewritten)

    def test_the_rewrite_actually_crosses_the_threshold(self):
        # Measured: 0.248 before, 0.620 after.
        self.assertEqual(grade(USER_PHRASING, CORPUS[0]), "irrelevant")
        self.assertEqual(grade(rewrite_query(USER_PHRASING, VOCABULARY), CORPUS[0]), "relevant")

    def test_is_case_insensitive(self):
        self.assertIn("payment method", rewrite_query("WHAT DOES ERROR 402 MEAN", VOCABULARY))

    def test_leaves_a_question_it_has_no_mapping_for_alone(self):
        self.assertEqual(
            rewrite_query(OFF_TOPIC, VOCABULARY),
            OFF_TOPIC,
            "returning something different anyway would send the second attempt "
            "somewhere arbitrary",
        )


class TestNeedsRetrieval(unittest.TestCase):
    def test_a_real_question_needs_it(self):
        self.assertTrue(needs_retrieval(USER_PHRASING))

    def test_thanks_does_not(self):
        for message in ["Thanks!", "thank you", "ok great", "Hello"]:
            self.assertFalse(needs_retrieval(message), message)

    def test_when_unsure_it_retrieves(self):
        # Short, and not obviously conversational.
        self.assertTrue(
            needs_retrieval("refund policy?"),
            "an unnecessary retrieval costs tokens; a skipped necessary one "
            "costs a wrong answer delivered confidently",
        )

    def test_a_long_message_always_retrieves(self):
        self.assertTrue(needs_retrieval("thanks thanks thanks thanks"))

    def test_empty_retrieves(self):
        self.assertTrue(needs_retrieval(""))


class TestTheCorrectiveLoop(unittest.TestCase):
    def test_a_first_attempt_that_works_does_not_re_query(self):
        result = answer(CORPUS_PHRASING, CORPUS, VOCABULARY)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["queries"], [CORPUS_PHRASING])

    def test_a_bad_first_attempt_is_rescued_by_the_rewrite(self):
        result = answer(USER_PHRASING, CORPUS, VOCABULARY)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(result["queries"]), 2)
        self.assertIn("payment method rejected", result["queries"][1])

    def test_it_says_it_does_not_know_rather_than_answering_anyway(self):
        result = answer(OFF_TOPIC, CORPUS, VOCABULARY)
        self.assertEqual(
            result["status"],
            "no_answer",
            "the answer nobody implements, and the correct one when the corpus "
            "genuinely lacks the fact",
        )
        self.assertEqual(result["chunks"], [])

    def test_conversational_messages_skip_the_pipeline(self):
        result = answer("Thanks, that helped", CORPUS, VOCABULARY)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(result["chunks"], [])

    def test_the_loop_is_bounded(self):
        result = answer(OFF_TOPIC, CORPUS, VOCABULARY, max_attempts=5)
        self.assertLessEqual(
            result["attempts"],
            5,
            "a loop that keeps rewriting until it finds something will "
            "eventually find something",
        )

    def test_it_stops_when_the_rewrite_changes_nothing(self):
        # No mapping matches, so a second search would be the same search.
        result = answer(OFF_TOPIC, CORPUS, VOCABULARY, max_attempts=5)
        self.assertEqual(result["attempts"], 1)

    def test_it_records_what_it_actually_searched_for(self):
        result = answer(USER_PHRASING, CORPUS, VOCABULARY)
        self.assertEqual(
            result["queries"][0],
            USER_PHRASING,
            "the only way to see afterwards what the loop drifted into",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
