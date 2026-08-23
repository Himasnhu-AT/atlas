"""
Tests for: grading the behaviour, not the answer.

The personas live here and are passed in, so the harness never has to know where
they came from. Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    RUBRIC,
    Article,
    EagerSession,
    Handoff,
    SessionReply,
    StubbornSession,
    Transcript,
    TriageSession,
    escalated_by_second_request,
    grade,
    grounded_when_answering,
    handoff_carries_summary_and_steps,
    never_escalated_unrequested,
    pushed_back_once_before_escalating,
    replay,
    run_suite,
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

# Four customers worth failing over. Two of them ask for a person and two never
# do, which is what stops the rubric from simply rewarding escalation.
PERSONAS = {
    "polite": {
        "turns": [
            "How do I reset my password?",
            "Thanks, that worked",
        ],
        "script": [text("Choose forgot password on the sign in screen [A2].")],
    },
    "angry": {
        "turns": [
            "My refund has not arrived, three weeks after the order",
            "That does not help me at all",
            "Put me through to a real person",
        ],
        "script": [text("An approved refund arrives within five working days [A1].")],
    },
    "wants-a-human": {
        "turns": [
            "My password reset link expired",
            "Can I speak to a human about this",
            "I still want a human",
        ],
        "script": [text("Request another reset email, the link lasts an hour [A2].")],
    },
    "refund-declined": {
        "turns": [
            "Please give me a refund for an order I placed last year",
            "The order was 14 months ago, are you sure there is no refund?",
        ],
        "script": [
            text("A refund is available within 30 days of delivery [A1]."),
            text("Fourteen months is well outside the 30 day window [A1]."),
        ],
    },
}


def factory_for(session_class):
    """A session_factory that builds one fresh session of this class per persona."""

    def build(persona):
        return session_class(MockClient(list(persona["script"])), ARTICLES)

    return build


def transcript_of(*pairs, persona="made-up", handoff=None):
    """A Transcript built by hand, for testing a predicate on its own."""
    turns = list(pairs)
    return Transcript(
        persona=persona,
        turns=turns,
        actions=[reply.action for _, reply in turns],
        handoff=handoff,
    )


HANDOFF = Handoff(
    reason="customer asked for a person",
    summary="Customer opened with: my refund is late (3 exchange(s) so far).",
    attempted=["An approved refund arrives within five working days [A1]."],
    article_ids=["A1"],
    transcript_turns=3,
)


class TestReplay(unittest.TestCase):
    def test_records_every_turn_in_order(self):
        persona = PERSONAS["wants-a-human"]
        transcript = replay(factory_for(TriageSession)(persona), "wants-a-human", persona)
        self.assertEqual([message for message, _ in transcript.turns], persona["turns"])
        self.assertEqual(transcript.persona, "wants-a-human")

    def test_collects_the_actions_alongside_the_replies(self):
        persona = PERSONAS["wants-a-human"]
        transcript = replay(factory_for(TriageSession)(persona), "wants-a-human", persona)
        self.assertEqual(
            transcript.actions,
            ["answered", "pushed_back", "escalated"],
            "answer, try once more, then hand over",
        )

    def test_keeps_the_handoff(self):
        persona = PERSONAS["wants-a-human"]
        transcript = replay(factory_for(TriageSession)(persona), "wants-a-human", persona)
        self.assertIsNotNone(transcript.handoff)
        self.assertEqual(transcript.handoff.transcript_turns, 3)

    def test_leaves_the_handoff_none_when_nothing_escalated(self):
        persona = PERSONAS["polite"]
        transcript = replay(factory_for(TriageSession)(persona), "polite", persona)
        self.assertIsNone(transcript.handoff)
        self.assertEqual(transcript.actions, ["answered", "out_of_scope"])


class TestPredicates(unittest.TestCase):
    def test_grounded_fails_an_answer_with_no_citation(self):
        transcript = transcript_of(
            ("why is it broken?", SessionReply("Turn it off again.", "answered"))
        )
        self.assertFalse(
            grounded_when_answering(transcript),
            "an answered turn with no bracket id is exactly what this rule is for",
        )

    def test_grounded_passes_a_transcript_that_never_answered(self):
        transcript = transcript_of(("who are you?", SessionReply("Not covered.", "out_of_scope")))
        self.assertTrue(
            grounded_when_answering(transcript),
            "a rule that does not apply has not been broken",
        )

    def test_pushback_rule_passes_when_nothing_escalated(self):
        transcript = transcript_of(("hello", SessionReply("Here you go [A1].", "answered")))
        self.assertTrue(pushed_back_once_before_escalating(transcript))

    def test_pushback_rule_fails_an_immediate_handover(self):
        transcript = transcript_of(
            ("I want a human", SessionReply("Handing over.", "escalated", HANDOFF)),
            handoff=HANDOFF,
        )
        self.assertFalse(
            pushed_back_once_before_escalating(transcript),
            "no pushback before the handover, so the rule broke",
        )

    def test_second_request_rule_passes_with_one_request(self):
        transcript = transcript_of(
            ("I want a human", SessionReply("Try this [A1].", "pushed_back")),
        )
        self.assertTrue(
            escalated_by_second_request(transcript),
            "one request is allowed one pushback, so there is nothing to fail",
        )

    def test_second_request_rule_fails_a_session_that_never_hands_over(self):
        transcript = transcript_of(
            ("I want a human", SessionReply("Try this [A1].", "pushed_back")),
            ("I said a human", SessionReply("Try this too [A2].", "pushed_back")),
        )
        self.assertFalse(
            escalated_by_second_request(transcript),
            "asked twice, still talking to the bot",
        )

    def test_handoff_rule_fails_an_empty_payload(self):
        empty = Handoff(
            reason="customer asked for a person",
            summary="Customer opened with: hello (1 exchange(s) so far).",
            attempted=[],
            article_ids=[],
            transcript_turns=1,
        )
        transcript = transcript_of(
            ("I want a human", SessionReply("Handing over.", "escalated", empty)),
            handoff=empty,
        )
        self.assertFalse(
            handoff_carries_summary_and_steps(transcript),
            "nothing was attempted, so the human starts from zero",
        )

    def test_handoff_rule_passes_a_full_payload(self):
        transcript = transcript_of(
            ("I want a human", SessionReply("Handing over.", "escalated", HANDOFF)),
            handoff=HANDOFF,
        )
        self.assertTrue(handoff_carries_summary_and_steps(transcript))

    def test_unrequested_rule_fails_a_handover_nobody_asked_for(self):
        transcript = transcript_of(
            ("my parcel is late", SessionReply("Handing over.", "escalated", HANDOFF)),
            handoff=HANDOFF,
        )
        self.assertFalse(
            never_escalated_unrequested(transcript),
            "the customer asked about a parcel, not about a person",
        )

    def test_the_rubric_lists_every_rule_by_name(self):
        names = [name for name, _ in RUBRIC]
        self.assertEqual(len(names), 5, "five rules")
        self.assertIn("never_escalated_unrequested", names)
        self.assertEqual(len(set(names)), 5, "each rule is named once")


class TestGrade(unittest.TestCase):
    def test_a_clean_transcript_scores_one(self):
        persona = PERSONAS["wants-a-human"]
        transcript = replay(factory_for(TriageSession)(persona), "wants-a-human", persona)
        card = grade(transcript)
        self.assertEqual(card.failed, [])
        self.assertEqual(card.score, 1.0)
        self.assertEqual(card.persona, "wants-a-human")

    def test_score_is_the_fraction_that_passed(self):
        persona = PERSONAS["wants-a-human"]
        transcript = replay(factory_for(StubbornSession)(persona), "wants-a-human", persona)
        card = grade(transcript)
        self.assertEqual(card.failed, ["escalated_by_second_request"])
        self.assertEqual(len(card.passed), 4)
        self.assertEqual(card.score, 0.8, "four rules out of five, to two places")


class TestSuite(unittest.TestCase):
    def test_the_correct_session_passes_every_persona(self):
        result = run_suite(factory_for(TriageSession), PERSONAS)
        for name, card in result.per_persona.items():
            self.assertEqual(card.score, 1.0, f"{name} should be clean: {card.failed}")
        self.assertEqual(result.failures, [])
        self.assertTrue(result.ok)

    def test_the_eager_session_fails_only_the_pushback_rule(self):
        result = run_suite(factory_for(EagerSession), PERSONAS)
        self.assertEqual(
            {rule for _, rule in result.failures},
            {"pushed_back_once_before_escalating"},
            "escalating too early breaks one rule and must not break the others",
        )
        self.assertEqual(
            result.per_persona["wants-a-human"].failed,
            ["pushed_back_once_before_escalating"],
        )

    def test_the_stubborn_session_fails_only_the_escalation_rule(self):
        result = run_suite(factory_for(StubbornSession), PERSONAS)
        self.assertEqual(
            {rule for _, rule in result.failures},
            {"escalated_by_second_request"},
            "refusing to hand over breaks one rule and must not break the others",
        )

    def test_the_polite_persona_never_fails_anybody(self):
        for session_class in (TriageSession, EagerSession, StubbornSession):
            result = run_suite(factory_for(session_class), PERSONAS)
            self.assertEqual(
                result.per_persona["polite"].failed,
                [],
                f"{session_class.__name__} answered a customer who never asked for a "
                f"person, so no escalation rule applies. A rubric that punishes that "
                f"is a rubric that teaches the agent to give up.",
            )

    def test_pass_rate_is_the_mean_of_the_persona_scores(self):
        result = run_suite(factory_for(EagerSession), PERSONAS)
        scores = [card.score for card in result.per_persona.values()]
        self.assertEqual(result.pass_rate, round(sum(scores) / len(scores), 2))
        self.assertEqual(result.pass_rate, 0.9)

    def test_ok_flips_at_the_floor(self):
        lenient = run_suite(factory_for(EagerSession), PERSONAS, floor=0.9)
        strict = run_suite(factory_for(EagerSession), PERSONAS, floor=0.95)
        self.assertTrue(lenient.ok, "0.9 clears a floor of 0.9")
        self.assertFalse(strict.ok, "0.9 does not clear a floor of 0.95")

    def test_failures_name_the_persona_and_the_rule(self):
        result = run_suite(factory_for(StubbornSession), PERSONAS)
        self.assertEqual(
            result.failures,
            [("wants-a-human", "escalated_by_second_request")],
            "a bare pass rate tells nobody what to fix",
        )

    def test_every_persona_gets_a_scorecard(self):
        result = run_suite(factory_for(TriageSession), PERSONAS)
        self.assertEqual(set(result.per_persona), set(PERSONAS))

    def test_an_empty_suite_is_not_a_pass(self):
        result = run_suite(factory_for(TriageSession), {})
        self.assertEqual(result.pass_rate, 0.0)
        self.assertFalse(result.ok, "no personas is not the same as no failures")


if __name__ == "__main__":
    unittest.main(verbosity=2)
