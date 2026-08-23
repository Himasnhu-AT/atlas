"""
Tests for: the RAG pipeline.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    NO_ANSWER,
    SYSTEM_PROMPT,
    Answer,
    Chunk,
    Document,
    Hit,
    VectorStore,
    answer,
    build_messages,
    format_context,
    ingest,
)

DOCS = [
    Document(
        "pricing.md",
        "Pricing",
        "The Pro plan includes unlimited projects and priority support.\n\n"
        "The Pro plan costs $49 per month when billed annually.\n\n"
        "The Free plan is limited to three projects and community support only.",
    ),
    Document(
        "account.md",
        "Account",
        "To reset your password, open the login page and choose forgot password.\n\n"
        "Sessions expire after thirty days of inactivity.",
    ),
    Document(
        "company.md",
        "Company",
        "Our office is in Lisbon and we work on Western European Time.\n\n"
        "Support replies to every ticket within one business day.",
    ),
]

#: Small enough that every paragraph becomes its own chunk, which is what makes
#: the retrieval in these tests worth looking at.
CHUNK_SIZE = 90

#: Shares no words with anything in the corpus, so every chunk scores 0.
UNRELATED = "volcanic basalt sedimentary strata"


def fresh(script=None) -> tuple[MockClient, VectorStore]:
    client = MockClient(script or [])
    store = VectorStore(client)
    ingest(store, DOCS, max_size=CHUNK_SIZE)
    return client, store


class TestIngest(unittest.TestCase):
    def test_splits_every_document(self):
        client, store = fresh()
        self.assertEqual(len(store), 7)

    def test_returns_the_chunks_it_created(self):
        client = MockClient()
        chunks = ingest(VectorStore(client), DOCS, max_size=CHUNK_SIZE)
        self.assertEqual(len(chunks), 7)
        self.assertTrue(all(isinstance(chunk, Chunk) for chunk in chunks))

    def test_chunks_are_in_document_order(self):
        client = MockClient()
        chunks = ingest(VectorStore(client), DOCS, max_size=CHUNK_SIZE)
        self.assertEqual(
            [chunk.citation() for chunk in chunks],
            [
                "pricing.md#0",
                "pricing.md#1",
                "pricing.md#2",
                "account.md#0",
                "account.md#1",
                "company.md#0",
                "company.md#1",
            ],
        )

    def test_indexes_restart_for_each_document(self):
        client = MockClient()
        chunks = ingest(VectorStore(client), DOCS, max_size=CHUNK_SIZE)
        by_source: dict[str, list[int]] = {}
        for chunk in chunks:
            by_source.setdefault(chunk.metadata["source"], []).append(chunk.index)
        for source, indexes in by_source.items():
            self.assertEqual(
                indexes,
                list(range(len(indexes))),
                f"{source} should be numbered from 0: the index is a position "
                f"within its document, and (source, index) is the identifier",
            )

    def test_carries_the_metadata_a_citation_needs(self):
        client = MockClient()
        chunk = ingest(VectorStore(client), DOCS, max_size=CHUNK_SIZE)[0]
        self.assertEqual(chunk.metadata["source"], "pricing.md")
        self.assertEqual(chunk.metadata["title"], "Pricing")
        self.assertIn("section", chunk.metadata)

    def test_embeds_the_whole_corpus_in_one_request(self):
        client, _ = fresh()
        self.assertEqual(
            len(client.embedding_requests),
            1,
            "one add for every chunk, not one per document: ingest is the step "
            "that touches the entire corpus",
        )

    def test_an_empty_corpus_costs_nothing(self):
        client = MockClient()
        store = VectorStore(client)
        self.assertEqual(ingest(store, [], max_size=CHUNK_SIZE), [])
        self.assertEqual(len(store), 0)
        self.assertEqual(len(client.embedding_requests), 0)

    def test_the_store_can_find_a_specific_chunk(self):
        client, store = fresh()
        hit = store.search("How much does the Pro plan cost?", k=3)[1]
        self.assertIn("$49", hit.chunk.text)


class TestFormatContext(unittest.TestCase):
    def setUp(self):
        self.hits = [
            Hit(Chunk("The Pro plan costs $49 per month.", 1, {"source": "pricing.md"}), 0.5),
            Hit(Chunk("The Free plan allows three projects.", 2, {"source": "pricing.md"}), 0.3),
        ]

    def test_exact_layout(self):
        self.assertEqual(
            format_context(self.hits),
            "[1] pricing.md#1\nThe Pro plan costs $49 per month.\n\n"
            "[2] pricing.md#2\nThe Free plan allows three projects.",
        )

    def test_numbers_from_one(self):
        rendered = format_context(self.hits)
        self.assertTrue(rendered.startswith("[1] "))
        self.assertIn("[2] ", rendered)

    def test_blocks_are_separated_by_a_blank_line(self):
        self.assertIn(
            "\n\n[2]",
            format_context(self.hits),
            "without the blank line the two chunks read as one passage and the "
            "second one's facts get attributed to the first one's number",
        )

    def test_carries_the_citation_next_to_the_number(self):
        self.assertIn("[1] pricing.md#1", format_context(self.hits))

    def test_chunk_text_goes_in_unmodified(self):
        awkward = Hit(Chunk("Line one.\nLine two.", 0, {"source": "a.md"}), 0.9)
        self.assertIn("Line one.\nLine two.", format_context([awkward]))

    def test_no_hits(self):
        self.assertEqual(format_context([]), "(no context retrieved)")


class TestBuildMessages(unittest.TestCase):
    def setUp(self):
        self.hits = [Hit(Chunk("Body.", 0, {"source": "a.md"}), 0.9)]
        self.messages = build_messages("How much is Pro?", self.hits)

    def test_three_messages_in_order(self):
        self.assertEqual(
            [message["role"] for message in self.messages], ["system", "user", "user"]
        )

    def test_the_system_message_carries_the_grounding_rule(self):
        self.assertEqual(self.messages[0]["content"], SYSTEM_PROMPT)
        self.assertIn(
            NO_ANSWER,
            self.messages[0]["content"],
            "the model needs the exact sentence you want back when the context "
            "does not answer the question",
        )

    def test_the_context_message(self):
        self.assertEqual(
            self.messages[1]["content"], "Context:\n\n" + format_context(self.hits)
        )

    def test_the_question_comes_last_and_alone(self):
        self.assertEqual(
            self.messages[-1]["content"],
            "How much is Pro?",
            "the question goes at the end on its own: buried above a wall of "
            "retrieved text it competes with everything you just pasted",
        )

    def test_works_with_no_hits(self):
        messages = build_messages("anything", [])
        self.assertIn("(no context retrieved)", messages[1]["content"])
        self.assertEqual(messages[-1]["content"], "anything")


class TestAnswer(unittest.TestCase):
    def test_returns_the_model_reply(self):
        client, store = fresh([text("The Pro plan is $49 per month [2].")])
        result = answer(client, store, "How much does the Pro plan cost?")
        self.assertIsInstance(result, Answer)
        self.assertIn("$49", result.text)
        self.assertTrue(result.grounded)

    def test_sends_the_grounded_prompt(self):
        client, store = fresh([text("reply")])
        answer(client, store, "How much does the Pro plan cost?")
        sent = client.requests[0]["messages"]
        self.assertEqual(len(sent), 3)
        self.assertEqual(sent[0]["content"], SYSTEM_PROMPT)
        self.assertIn("$49", sent[1]["content"])

    def test_makes_exactly_one_model_call(self):
        client, store = fresh([text("reply")])
        answer(client, store, "How much does the Pro plan cost?")
        self.assertEqual(client.call_count, 1)

    def test_sources_come_from_the_hits(self):
        client, store = fresh([text("reply")])
        result = answer(client, store, "How much does the Pro plan cost?", k=2)
        self.assertEqual(result.sources, ["pricing.md#0", "pricing.md#1"])

    def test_sources_line_up_with_the_numbering(self):
        client, store = fresh([text("reply")])
        result = answer(client, store, "How much does the Pro plan cost?", k=2)
        context = client.requests[0]["messages"][1]["content"]
        self.assertIn(f"[1] {result.sources[0]}", context)
        self.assertIn(f"[2] {result.sources[1]}", context)

    def test_sources_do_not_depend_on_what_the_model_wrote(self):
        client, store = fresh([text("No citations anywhere in this reply.")])
        result = answer(client, store, "How much does the Pro plan cost?", k=1)
        self.assertEqual(
            result.sources,
            ["pricing.md#0"],
            "sources is a record of what your code sent, not a reading of what "
            "the model claimed; the two are checked against each other later",
        )

    def test_drops_hits_below_the_threshold(self):
        client, store = fresh([text("reply")])
        result = answer(client, store, "How much does the Pro plan cost?", k=3, min_score=0.25)
        self.assertEqual(
            len(result.sources), 2, "the third chunk scores below 0.25 and is not sent"
        )

    def test_declines_when_nothing_is_relevant(self):
        client, store = fresh([text("should never be reached")])
        result = answer(client, store, UNRELATED)
        self.assertEqual(result.text, NO_ANSWER)
        self.assertEqual(result.sources, [])
        self.assertFalse(result.grounded)

    def test_declining_costs_no_model_call(self):
        client, store = fresh([text("should never be reached")])
        answer(client, store, UNRELATED)
        self.assertEqual(
            client.call_count,
            0,
            "the instruction in the system prompt asks the model to decline; "
            "the threshold is the half of that promise you can enforce",
        )

    def test_declines_on_an_empty_store(self):
        client = MockClient([text("nope")])
        result = answer(client, VectorStore(client), "anything")
        self.assertEqual(result.text, NO_ANSWER)
        self.assertEqual(client.call_count, 0)

    def test_a_lower_threshold_lets_a_weak_match_through(self):
        client, store = fresh([text("an answer built from nothing in particular")])
        result = answer(client, store, UNRELATED, min_score=0.0)
        self.assertTrue(
            result.grounded,
            "with the floor removed there is always a least bad chunk, and this "
            "is what a confident wrong answer looks like from the inside",
        )
        self.assertEqual(client.call_count, 1)

    def test_an_empty_reply_is_not_turned_into_a_refusal(self):
        client, store = fresh([text("")])
        result = answer(client, store, "How much does the Pro plan cost?")
        self.assertEqual(
            result.text,
            "",
            "a grounded call that produced nothing is a different bug from a "
            "question you declined, and the log has to be able to tell them apart",
        )
        self.assertTrue(result.grounded)

    def test_rejects_a_nonsense_k(self):
        client, store = fresh([text("x")])
        with self.assertRaises(ValueError):
            answer(client, store, "anything", k=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
