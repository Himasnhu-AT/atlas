"""
Tests for: vector search.

Run with `python3 test.py`.

The MockClient here is built with no chat script, so it can serve embeddings and
nothing else. If one of these tests fails with ScriptExhausted, something in your
code is calling the chat API, and retrieval has no business doing that.
"""

from __future__ import annotations

import unittest

from mockllm import EMBEDDING_DIMENSIONS, MockClient

from solution import (
    AMBIGUOUS,
    CONFIDENT,
    NO_MATCH,
    Document,
    Hit,
    Index,
    Verdict,
    assess,
    build_index,
    search,
    search_above,
)

DOCS = [
    Document(
        "billing-refunds",
        "Refunds are issued to the original payment method within ten business "
        "days of approval.",
    ),
    Document(
        "billing-refunds-eu",
        "Refunds for EU customers are issued to the original payment method "
        "within fourteen business days.",
    ),
    Document(
        "billing-invoices",
        "Invoices are generated on the first business day of each month and "
        "emailed to the billing contact.",
    ),
    Document(
        "auth-reset",
        "To reset your password, open the login page and choose forgot password.",
    ),
    Document(
        "auth-sessions",
        "Sessions expire after thirty days of inactivity and you will be asked "
        "to sign in again.",
    ),
]


def fresh() -> tuple[MockClient, Index]:
    client = MockClient()
    return client, build_index(client, DOCS)


def scores_by_id(hits: list[Hit]) -> dict[str, float]:
    return {hit.document.id: hit.score for hit in hits}


class TestBuildIndex(unittest.TestCase):
    def test_stores_one_vector_per_document(self):
        _, index = fresh()
        self.assertEqual(len(index.documents), len(DOCS))
        self.assertEqual(len(index.vectors), len(DOCS))

    def test_vectors_have_the_model_dimensions(self):
        _, index = fresh()
        for vector in index.vectors:
            self.assertEqual(len(vector), EMBEDDING_DIMENSIONS)

    def test_embeds_the_whole_batch_in_one_call(self):
        client, _ = fresh()
        self.assertEqual(
            len(client.embedding_requests),
            1,
            "one request for the batch, not one request per document: embedding "
            "APIs are rate limited per request as well as per token",
        )

    def test_sends_every_document_text(self):
        client, _ = fresh()
        self.assertEqual(client.embedding_requests[0], [doc.text for doc in DOCS])

    def test_an_empty_corpus_costs_nothing(self):
        client = MockClient()
        index = build_index(client, [])
        self.assertEqual(index.documents, [])
        self.assertEqual(index.vectors, [])
        self.assertEqual(
            len(client.embedding_requests), 0, "an empty batch is still a round trip"
        )

    def test_vectors_are_paired_with_the_right_documents(self):
        # Searching for a document's own text should return that document with a
        # near perfect score. If the pairing has slipped, this finds it.
        client, index = fresh()
        hits = search(client, index, DOCS[2].text, k=1)
        self.assertEqual(hits[0].document.id, "billing-invoices")
        self.assertAlmostEqual(hits[0].score, 1.0, places=6)


class TestSearch(unittest.TestCase):
    def test_empty_index_returns_nothing(self):
        client = MockClient()
        self.assertEqual(search(client, Index(), "anything"), [])

    def test_zero_k_returns_nothing(self):
        client, index = fresh()
        self.assertEqual(search(client, index, "refunds", k=0), [])

    def test_k_larger_than_the_index(self):
        client, index = fresh()
        self.assertEqual(len(search(client, index, "refunds", k=99)), len(DOCS))

    def test_returns_k_hits(self):
        client, index = fresh()
        self.assertEqual(len(search(client, index, "refunds", k=2)), 2)

    def test_ranks_best_first(self):
        client, index = fresh()
        scores = [hit.score for hit in search(client, index, "business days", k=5)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_finds_the_relevant_document(self):
        client, index = fresh()
        hits = search(client, index, "how do I reset my password", k=1)
        self.assertEqual(hits[0].document.id, "auth-reset")

    def test_embeds_the_query_through_the_same_client(self):
        client, index = fresh()
        before = len(client.embedding_requests)
        search(client, index, "refunds", k=1)
        self.assertEqual(
            len(client.embedding_requests),
            before + 1,
            "the query has to go through the same embedding model as the "
            "documents, or the vectors are not in the same space",
        )

    def test_is_deterministic(self):
        client, index = fresh()
        first = [hit.document.id for hit in search(client, index, "business days", k=5)]
        second = [hit.document.id for hit in search(client, index, "business days", k=5)]
        self.assertEqual(first, second)

    def test_ties_break_toward_the_document_added_first(self):
        client = MockClient()
        index = build_index(
            client,
            [Document("first", "identical text"), Document("second", "identical text")],
        )
        hits = search(client, index, "identical text", k=2)
        self.assertEqual(
            [hit.document.id for hit in hits],
            ["first", "second"],
            "equal scores must resolve the same way every run, or every test "
            "above retrieval becomes flaky",
        )

    def test_ranks_without_judging(self):
        client, index = fresh()
        hits = search(client, index, "photosynthesis chlorophyll mitochondria", k=3)
        self.assertEqual(
            len(hits), 3, "search ranks; deciding what is good enough is search_above"
        )


class TestSearchAbove(unittest.TestCase):
    def test_drops_the_weak_hits(self):
        client, index = fresh()
        hits = search_above(client, index, "how do I reset my password", k=5)
        self.assertEqual([hit.document.id for hit in hits], ["auth-reset"])

    def test_returns_nothing_rather_than_the_least_bad_match(self):
        client, index = fresh()
        self.assertEqual(
            search_above(client, index, "photosynthesis chlorophyll mitochondria", k=3),
            [],
            "there is always a least bad document; returning it is how an "
            "unanswerable question becomes a confident wrong answer",
        )

    def test_a_hit_exactly_on_the_line_survives(self):
        client, index = fresh()
        top = search(client, index, "business days", k=1)[0]
        hits = search_above(client, index, "business days", k=1, threshold=top.score)
        self.assertEqual(len(hits), 1, "the comparison is >=, not >")

    def test_k_is_applied_before_the_threshold(self):
        client, index = fresh()
        hits = search_above(client, index, "refunds within ten business days", k=1)
        self.assertEqual(
            len(hits),
            1,
            "k is how much context you can afford and the threshold is what "
            "counts as a match: they are separate decisions",
        )

    def test_a_threshold_of_zero_keeps_everything_scoring_anything(self):
        client, index = fresh()
        hits = search_above(client, index, "business days", k=5, threshold=0.0)
        self.assertEqual(len(hits), 5)


class TestAssess(unittest.TestCase):
    def test_confident_on_a_single_clear_hit(self):
        client, index = fresh()
        verdict = assess(client, index, "how do I reset my password")
        self.assertIsInstance(verdict, Verdict)
        self.assertEqual(verdict.label, CONFIDENT)
        self.assertEqual(verdict.hits[0].document.id, "auth-reset")

    def test_a_single_hit_has_no_margin(self):
        client, index = fresh()
        verdict = assess(client, index, "how do I reset my password")
        self.assertIsNone(
            verdict.margin,
            "with one hit there is nothing to compare against; a margin of 0.0 "
            "would read as a dead heat",
        )

    def test_confident_when_the_top_hit_is_clear_of_the_second(self):
        client, index = fresh()
        verdict = assess(client, index, "refunds within ten business days of approval")
        self.assertEqual(verdict.label, CONFIDENT)
        self.assertEqual(verdict.hits[0].document.id, "billing-refunds")
        self.assertGreater(verdict.margin, 0.05)

    def test_ambiguous_when_the_top_two_are_close(self):
        client, index = fresh()
        verdict = assess(client, index, "invoices business days")
        self.assertEqual(
            verdict.label,
            AMBIGUOUS,
            "three documents mention business days and the retriever cannot "
            "tell which one the question is about",
        )
        self.assertLess(verdict.margin, 0.05)

    def test_the_ambiguous_query_ranks_the_right_document_third(self):
        # Worth seeing rather than reading about: the question is about
        # invoices, and both refund documents beat the invoice document on
        # shared words alone.
        client, index = fresh()
        verdict = assess(client, index, "invoices business days")
        self.assertEqual(
            [hit.document.id for hit in verdict.hits][:3],
            ["billing-refunds", "billing-refunds-eu", "billing-invoices"],
        )

    def test_no_match_on_an_unrelated_query(self):
        client, index = fresh()
        verdict = assess(client, index, "photosynthesis chlorophyll mitochondria")
        self.assertEqual(verdict.label, NO_MATCH)
        self.assertEqual(verdict.hits, [])
        self.assertIsNone(verdict.margin)

    def test_a_paraphrased_question_finds_nothing(self):
        # "money back" and "refunds" are the same idea and share no words, so
        # these hashed embeddings score them at zero. A trained embedding model
        # would put them close. The behaviour to notice is not the miss, it is
        # what the code does about it.
        client, index = fresh()
        ranked = scores_by_id(search(client, index, "how long until I get my money back", k=5))
        self.assertAlmostEqual(
            ranked["billing-refunds"],
            0.0,
            places=6,
            msg="the document that answers the question shares no words with it",
        )

    def test_the_paraphrased_question_reports_no_match_rather_than_guessing(self):
        client, index = fresh()
        verdict = assess(client, index, "how long until I get my money back")
        self.assertEqual(
            verdict.label,
            NO_MATCH,
            "the best scoring document is about session expiry and matched on "
            "'you will I be'; a threshold is what stops that reaching a prompt",
        )

    def test_lowering_the_threshold_lets_the_wrong_document_through(self):
        client, index = fresh()
        verdict = assess(client, index, "how long until I get my money back", threshold=0.1)
        self.assertEqual(verdict.label, CONFIDENT)
        self.assertEqual(
            verdict.hits[0].document.id,
            "auth-sessions",
            "confidently wrong: the threshold is the only thing standing between "
            "this and an answer about sessions to a question about refunds",
        )

    def test_min_margin_is_configurable(self):
        client, index = fresh()
        verdict = assess(
            client, index, "refunds within ten business days of approval", min_margin=0.9
        )
        self.assertEqual(verdict.label, AMBIGUOUS)

    def test_never_calls_the_chat_api(self):
        client, index = fresh()
        assess(client, index, "how do I reset my password")
        self.assertEqual(
            client.call_count, 0, "retrieval is arithmetic; no model is involved"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
