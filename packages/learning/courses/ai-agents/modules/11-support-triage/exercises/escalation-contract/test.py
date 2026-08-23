"""
Tests for: when to hand over.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Article,
    HUMAN_QUEUE,
    OUT_OF_SCOPE_TEXT,
    TriageSession,
    summarise,
    wants_human,
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

EXPIRED = "My password reset link expired"
RESET = "How do I reset my password?"
OFF_TOPIC = "Do you sponsor conference booths?"
ASK = "Can I speak to a human about this"
ASK_AGAIN = "I still want a human"

RESET_ANSWER = "Request another reset email, the link expires after an hour [A2]."


def session(script, **kwargs):
    """A session over the fixture corpus with a scripted client."""
    return TriageSession(MockClient(list(script)), ARTICLES, **kwargs)


class TestWantsHuman(unittest.TestCase):
    def test_matches_a_plain_request(self):
        self.assertTrue(wants_human(ASK))

    def test_matches_the_multi_word_phrases(self):
        self.assertTrue(wants_human("Put me through to a real person"))
        self.assertTrue(wants_human("I would rather talk to someone else"))
        self.assertTrue(wants_human("Get me a representative"))

    def test_is_case_insensitive(self):
        self.assertTrue(wants_human("I WANT A HUMAN"))

    def test_ignores_a_user_agent_string(self):
        self.assertFalse(
            wants_human("my user agent string is broken"),
            "a pasted log line is not a request for a person",
        )

    def test_needs_a_whole_word(self):
        self.assertFalse(
            wants_human("this is a question about humanities funding"),
            "'human' inside 'humanities' is not a request",
        )

    def test_an_ordinary_question_is_not_a_request(self):
        self.assertFalse(wants_human(EXPIRED))


class TestSummarise(unittest.TestCase):
    def test_quotes_the_first_customer_message(self):
        line = summarise([("user", EXPIRED), ("agent", RESET_ANSWER), ("user", ASK)])
        self.assertIn(EXPIRED, line, "the human reads this before anything else")

    def test_counts_the_exchanges(self):
        line = summarise([("user", EXPIRED), ("agent", RESET_ANSWER), ("user", ASK)])
        self.assertIn("2", line, "two user messages is two exchanges")

    def test_is_one_line(self):
        line = summarise([("user", "first\nsecond\nthird"), ("agent", "ok")])
        self.assertNotIn("\n", line, "a summary that wraps is not a summary")

    def test_survives_an_empty_transcript(self):
        line = summarise([])
        self.assertIsInstance(line, str)
        self.assertNotEqual(line.strip(), "")


class TestOrdinaryTurns(unittest.TestCase):
    def test_an_answered_question_is_recorded(self):
        agent = session([text(RESET_ANSWER)])
        reply = agent.handle(EXPIRED)
        self.assertEqual(reply.action, "answered")
        self.assertEqual(reply.text, RESET_ANSWER)
        self.assertIsNone(reply.handoff)
        self.assertEqual(agent.attempted, [RESET_ANSWER])
        self.assertEqual(agent.cited, ["A2"])
        self.assertFalse(agent.escalated)

    def test_an_ungrounded_reply_is_not_sent_to_the_customer(self):
        agent = session([text("Just turn it off and on again.")])
        reply = agent.handle(EXPIRED)
        self.assertEqual(reply.action, "out_of_scope")
        self.assertEqual(
            reply.text,
            OUT_OF_SCOPE_TEXT,
            "a reply grounded in nothing does not go to the customer",
        )
        self.assertEqual(
            agent.attempted,
            ["Just turn it off and on again."],
            "the draft is still recorded, so a human can see what was nearly sent",
        )

    def test_an_out_of_scope_question_costs_no_model_call(self):
        agent = session([])
        reply = agent.handle(OFF_TOPIC)
        self.assertEqual(reply.action, "out_of_scope")
        self.assertEqual(agent.client.call_count, 0)

    def test_the_transcript_records_both_sides(self):
        agent = session([text(RESET_ANSWER)])
        agent.handle(EXPIRED)
        self.assertEqual(
            agent.transcript,
            [("user", EXPIRED), ("agent", RESET_ANSWER)],
            "the log a human reads is the conversation, not half of it",
        )


class TestPushback(unittest.TestCase):
    def test_the_first_request_pushes_back(self):
        agent = session([text(RESET_ANSWER)])
        agent.handle(EXPIRED)
        reply = agent.handle(ASK)
        self.assertEqual(reply.action, "pushed_back")
        self.assertIsNone(reply.handoff, "a pushback is not a handoff")
        self.assertFalse(agent.escalated)
        self.assertEqual(agent.human_requests, 1)

    def test_the_pushback_offers_the_article_for_the_last_real_question(self):
        agent = session([text(RESET_ANSWER)])
        agent.handle(EXPIRED)
        reply = agent.handle(ASK)
        self.assertIn(
            "[A2]",
            reply.text,
            "the customer's question is still the question, so offer the article "
            "for it rather than for the words 'can I speak to a human'",
        )

    def test_a_pushback_with_no_match_still_offers_a_way_forward(self):
        agent = session([])
        reply = agent.handle("Put me through to a real person")
        self.assertEqual(reply.action, "pushed_back")
        self.assertIn(HUMAN_QUEUE, reply.text)
        self.assertEqual(agent.client.call_count, 0, "a pushback needs no model call")

    def test_the_pushback_counts_as_something_attempted(self):
        agent = session([text(RESET_ANSWER)])
        agent.handle(EXPIRED)
        reply = agent.handle(ASK)
        self.assertEqual(agent.attempted, [RESET_ANSWER, reply.text])


class TestEscalation(unittest.TestCase):
    def _escalated(self):
        agent = session([text(RESET_ANSWER)])
        agent.handle(EXPIRED)
        agent.handle(ASK)
        return agent, agent.handle(ASK_AGAIN)

    def test_the_second_request_escalates(self):
        agent, reply = self._escalated()
        self.assertEqual(reply.action, "escalated")
        self.assertTrue(agent.escalated)
        self.assertIsNotNone(reply.handoff, "escalating without a payload is the bug")

    def test_the_handoff_lists_everything_attempted(self):
        agent, reply = self._escalated()
        self.assertEqual(
            len(reply.handoff.attempted),
            2,
            "the answer and the pushback both count, so the human does not repeat them",
        )
        self.assertEqual(reply.handoff.attempted[0], RESET_ANSWER)

    def test_the_handoff_carries_the_cited_articles_without_duplicates(self):
        agent = session([text(RESET_ANSWER), text("Try the forgot password link [A2].")])
        agent.handle(EXPIRED)
        agent.handle(RESET)
        agent.handle(ASK)
        reply = agent.handle(ASK_AGAIN)
        self.assertEqual(
            reply.handoff.article_ids,
            ["A2"],
            "A2 was cited twice and appears once",
        )

    def test_the_handoff_summary_quotes_the_opening_message(self):
        agent, reply = self._escalated()
        self.assertIn(EXPIRED, reply.handoff.summary)

    def test_the_handoff_counts_the_customer_turns(self):
        agent, reply = self._escalated()
        self.assertEqual(
            reply.handoff.transcript_turns,
            3,
            "three messages from the customer, whatever the agent said back",
        )

    def test_the_handoff_is_a_snapshot(self):
        agent, reply = self._escalated()
        before = list(reply.handoff.attempted)
        agent.attempted.append("something later")
        self.assertEqual(
            reply.handoff.attempted,
            before,
            "copy the lists into the handoff, do not alias them",
        )

    def test_a_session_that_never_asks_never_escalates(self):
        agent = session([text(RESET_ANSWER)] * 4)
        for _ in range(4):
            reply = agent.handle(EXPIRED)
            self.assertEqual(reply.action, "answered")
        self.assertFalse(
            agent.escalated,
            "length is not a reason to escalate. Only asking is.",
        )

    def test_the_model_is_never_called_after_escalation(self):
        agent, reply = self._escalated()
        calls = agent.client.call_count
        after = agent.handle(EXPIRED)
        self.assertEqual(after.action, "escalated")
        self.assertEqual(
            agent.client.call_count,
            calls,
            "a person owns this conversation now, so stop talking over them",
        )

    def test_the_same_handoff_comes_back_every_time(self):
        agent, reply = self._escalated()
        again = agent.handle("are you still there?")
        self.assertIs(
            again.handoff,
            reply.handoff,
            "one escalation, one payload. Rebuilding it invents a second ticket.",
        )

    def test_zero_pushbacks_escalates_on_the_first_request(self):
        agent = session([], max_pushbacks=0)
        reply = agent.handle(ASK)
        self.assertEqual(reply.action, "escalated")
        self.assertEqual(agent.human_requests, 1)
        self.assertEqual(
            reply.handoff.attempted,
            [],
            "nothing had been tried yet, and the handoff says so honestly",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
