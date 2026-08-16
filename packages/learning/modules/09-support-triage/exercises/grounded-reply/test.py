"""
Tests for: grounded answers and the scope boundary.

The knowledge base lives here, not on disk, and it is passed in to everything
that needs it. Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Article,
    HUMAN_QUEUE,
    SYSTEM,
    answer,
    build_messages,
    parse_citations,
    retrieve,
)

ARTICLES = [
    Article(
        "A1",
        "Refund window",
        "A refund is available within 30 days of delivery. A refund requested after 30 "
        "days is declined unless a warranty claim covers the order. An approved refund "
        "arrives on the original payment method within five working days.",
    ),
    Article(
        "A2",
        "Password reset",
        "Choose forgot password on the sign in screen to receive a reset email. The "
        "reset link expires one hour after it is sent. Request another reset email if "
        "the link expired.",
    ),
    Article(
        "A3",
        "Delivery times",
        "Standard delivery arrives in three to five working days. A tracking number is "
        "emailed when the parcel leaves the warehouse. Express delivery is next working "
        "day when ordered before noon.",
    ),
    Article(
        "A4",
        "Invoices and billing",
        "Enterprise plans are invoiced monthly in arrears. Change the billing contact "
        "from account settings. Invoices download as PDF for the last 24 months.",
    ),
]

PASSWORD = "How do I reset my password?"
REFUND = "My refund has not arrived, three weeks after the order"
OFF_TOPIC = "Do you sponsor conference booths?"


class TestRetrieve(unittest.TestCase):
    def test_puts_the_matching_article_first(self):
        hits = retrieve(ARTICLES, PASSWORD)
        self.assertTrue(hits, "the password article should score above the floor")
        self.assertEqual(hits[0][0].id, "A2", "A2 is the password reset article")

    def test_scores_descend(self):
        hits = retrieve(ARTICLES, REFUND, k=4)
        scores = [score for _, score in hits]
        self.assertEqual(scores, sorted(scores, reverse=True), "best hit comes first")

    def test_honours_k(self):
        self.assertEqual(len(retrieve(ARTICLES, REFUND, k=1)), 1)
        self.assertEqual([a.id for a, _ in retrieve(ARTICLES, REFUND, k=1)], ["A1"])

    def test_drops_everything_below_the_floor(self):
        self.assertEqual(
            retrieve(ARTICLES, OFF_TOPIC),
            [],
            "a question the corpus knows nothing about must retrieve nothing",
        )

    def test_a_higher_floor_keeps_less(self):
        loose = retrieve(ARTICLES, REFUND, k=4, floor=0.12)
        strict = retrieve(ARTICLES, REFUND, k=4, floor=0.3)
        self.assertGreater(len(loose), len(strict), "floor is a filter, not a suggestion")
        self.assertEqual([a.id for a, _ in strict], ["A1"])

    def test_breaks_ties_on_article_id(self):
        twins = [
            Article("A9", "Duplicate note", "refund window duplicate text"),
            Article("A5", "Duplicate note", "refund window duplicate text"),
        ]
        hits = retrieve(twins, "refund window", k=2)
        self.assertEqual(
            [a.id for a, _ in hits],
            ["A5", "A9"],
            "identical scores must order by id ascending, not by corpus order",
        )

    def test_does_not_mutate_the_corpus(self):
        before = [(a.id, a.title, a.body) for a in ARTICLES]
        retrieve(ARTICLES, REFUND, k=4)
        after = [(a.id, a.title, a.body) for a in ARTICLES]
        self.assertEqual(before, after, "retrieval reads the corpus, it does not edit it")


class TestBuildMessages(unittest.TestCase):
    def setUp(self):
        self.hits = retrieve(ARTICLES, REFUND, k=2)
        self.messages = build_messages(REFUND, self.hits, SYSTEM)

    def test_opens_with_the_system_prompt(self):
        self.assertEqual(self.messages[0], {"role": "system", "content": SYSTEM})

    def test_ends_with_the_question_alone(self):
        self.assertEqual(
            self.messages[-1],
            {"role": "user", "content": REFUND},
            "the question is the last message and carries nothing else",
        )

    def test_carries_every_hit_with_its_bracket_id(self):
        context = self.messages[1]["content"]
        for article, _ in self.hits:
            self.assertIn(f"[{article.id}]", context, "each hit is labelled with its id")
            self.assertIn(article.body, context, "the body is what the model answers from")

    def test_is_three_messages(self):
        self.assertEqual(
            len(self.messages), 3, "system, context, question. Nothing else."
        )


class TestParseCitations(unittest.TestCase):
    def test_keeps_first_appearance_order_without_duplicates(self):
        cited, dropped = parse_citations(
            "The window is 30 days [A1]. Refunds clear in five days [A2], "
            "counted from approval [A1].",
            ["A1", "A2"],
        )
        self.assertEqual(cited, ["A1", "A2"], "first appearance order, deduplicated")
        self.assertEqual(dropped, [])

    def test_separates_ids_that_were_never_retrieved(self):
        cited, dropped = parse_citations("Try this [A2], and also [A9].", ["A2"])
        self.assertEqual(cited, ["A2"])
        self.assertEqual(dropped, ["A9"], "A9 was never retrieved, so it was invented")

    def test_a_reply_with_no_markers(self):
        self.assertEqual(parse_citations("Sure, happy to help.", ["A1"]), ([], []))

    def test_ignores_brackets_that_are_not_citations(self):
        cited, dropped = parse_citations("Run [main] then check [A1].", ["A1"])
        self.assertEqual(cited, ["A1"])
        self.assertEqual(dropped, [], "[main] is not a citation marker")


class TestAnswer(unittest.TestCase):
    def test_returns_the_model_text_and_its_citations(self):
        client = MockClient(
            [text("Choose forgot password on the sign in screen [A2].")]
        )
        reply = answer(client, ARTICLES, PASSWORD)
        self.assertEqual(reply.route, "answered")
        self.assertEqual(reply.cited, ["A2"])
        self.assertEqual(reply.dropped, [])
        self.assertEqual(reply.text, "Choose forgot password on the sign in screen [A2].")
        self.assertEqual(client.call_count, 1, "one question, one model call")

    def test_sends_the_retrieved_context_to_the_model(self):
        client = MockClient([text("Reset it from the sign in screen [A2].")])
        answer(client, ARTICLES, PASSWORD)
        sent = client.requests[0]["messages"]
        self.assertEqual(sent[0]["role"], "system")
        self.assertIn("[A2]", sent[1]["content"], "the context must carry the ids")
        self.assertEqual(sent[-1]["content"], PASSWORD)

    def test_out_of_scope_never_calls_the_model(self):
        client = MockClient([text("Absolutely, we love conferences.")])
        reply = answer(client, ARTICLES, OFF_TOPIC)
        self.assertEqual(reply.route, "out_of_scope")
        self.assertEqual(
            client.call_count,
            0,
            "retrieval was empty, so the answer could not be grounded whatever "
            "the model said. Do not pay for that call.",
        )

    def test_out_of_scope_names_the_human_queue(self):
        reply = answer(MockClient([]), ARTICLES, OFF_TOPIC)
        self.assertIn(
            HUMAN_QUEUE,
            reply.text,
            "out of scope is a route to somebody, not a dead end",
        )
        self.assertEqual(reply.cited, [])
        self.assertEqual(reply.dropped, [])

    def test_an_invented_citation_is_dropped(self):
        client = MockClient(
            [text("Request another email [A2]. Support can force a reset [A9].")]
        )
        reply = answer(client, ARTICLES, PASSWORD)
        self.assertEqual(reply.cited, ["A2"])
        self.assertEqual(reply.dropped, ["A9"], "A9 was never retrieved for this question")
        self.assertNotIn("A9", reply.cited)

    def test_a_reply_that_cites_nothing_is_unsupported(self):
        client = MockClient([text("Just turn it off and on again.")])
        reply = answer(client, ARTICLES, PASSWORD)
        self.assertEqual(
            reply.route,
            "unsupported",
            "an answer with no citation is a failure, not an answer",
        )
        self.assertEqual(reply.cited, [])
        self.assertEqual(
            reply.text,
            "Just turn it off and on again.",
            "keep the text: a human needs to see what the agent nearly sent",
        )

    def test_an_empty_reply_does_not_crash(self):
        client = MockClient([text("")])
        reply = answer(client, ARTICLES, PASSWORD)
        self.assertEqual(reply.route, "unsupported")
        self.assertEqual(reply.text, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
