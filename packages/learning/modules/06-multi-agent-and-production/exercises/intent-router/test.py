"""
Tests for: an intent router.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    Decision,
    Handoff,
    MalformedReply,
    Route,
    Router,
    build_router_messages,
    model_route,
    normalise,
    parse_label,
    rule_route,
)


def recorder(label: str):
    """A handler that echoes the request it was handed, tagged with its route."""

    def handler(handoff: Handoff) -> str:
        return f"{label}: {handoff.request}"

    return handler


BILLING = Route(
    name="billing",
    description="Invoices, refunds, card charges and plan changes.",
    handler=recorder("billing"),
    keywords=("refund", "invoice", "charge", "password reset"),
)
TECH = Route(
    name="tech",
    description="Crashes, errors and anything that stopped working.",
    handler=recorder("tech"),
    keywords=("error", "crash", "broken"),
)
GENERAL = Route(
    name="general",
    description="Anything that does not clearly belong elsewhere.",
    handler=recorder("general"),
    keywords=(),
)
ROUTES = [BILLING, TECH, GENERAL]


def reply(route: str, confidence: float) -> str:
    return '{"route": "%s", "confidence": %s}' % (route, confidence)


def router(*script, **kwargs):
    kwargs.setdefault("fallback", "general")
    return Router(MockClient(list(script)), ROUTES, **kwargs)


class TestParsing(unittest.TestCase):
    def test_normalise_lowercases_and_splits(self):
        self.assertEqual(normalise("Refund, PLEASE!"), {"refund", "please"})

    def test_normalise_of_empty_is_empty(self):
        self.assertEqual(normalise(""), set())

    def test_parses_a_plain_object(self):
        self.assertEqual(parse_label(reply("billing", 0.9)), ("billing", 0.9))

    def test_parses_through_a_code_fence(self):
        fenced = '```json\n{"route": "tech", "confidence": 0.7}\n```'
        self.assertEqual(
            parse_label(fenced),
            ("tech", 0.7),
            "models wrap JSON in a fence whatever the prompt says; strip it",
        )

    def test_rejects_non_json(self):
        with self.assertRaises(MalformedReply):
            parse_label("I think this one is about billing.")

    def test_rejects_a_missing_confidence(self):
        with self.assertRaises(MalformedReply):
            parse_label('{"route": "billing"}')

    def test_rejects_a_confidence_out_of_range(self):
        with self.assertRaises(MalformedReply):
            parse_label('{"route": "billing", "confidence": 42}')

    def test_rejects_no_content(self):
        with self.assertRaises(MalformedReply):
            parse_label(None)


class TestRuleRoute(unittest.TestCase):
    def test_routes_on_one_keyword(self):
        decision = rule_route(ROUTES, "I need a refund")
        self.assertEqual(decision.route, "billing")
        self.assertEqual(decision.reason, "rule")
        self.assertEqual(decision.matched, ("refund",))

    def test_confidence_is_the_fraction_of_keywords_matched(self):
        decision = rule_route(ROUTES, "my invoice shows a wrong charge")
        self.assertAlmostEqual(decision.confidence, 0.5, msg="two of four keywords")

    def test_matched_keeps_the_routes_own_order(self):
        decision = rule_route(ROUTES, "charge and invoice and refund")
        self.assertEqual(decision.matched, ("refund", "invoice", "charge"))

    def test_a_multi_word_keyword_needs_every_word(self):
        self.assertIsNone(rule_route(ROUTES, "reset my session"))
        self.assertEqual(rule_route(ROUTES, "reset my password").route, "billing")

    def test_no_match_returns_none(self):
        self.assertIsNone(
            rule_route(ROUTES, "what is the capital of France"),
            "no rule fired, so the rule pass has no opinion",
        )

    def test_a_tie_returns_none(self):
        decision = rule_route(ROUTES, "a refund because of a crash")
        self.assertIsNone(
            decision,
            "billing and tech both matched one keyword. Breaking the tie on list "
            "order turns an ambiguity into a confident mistake; decline instead",
        )

    def test_makes_no_model_call(self):
        client = MockClient([text("should never be read")])
        Router(client, ROUTES, fallback="general").decide("I need a refund")
        self.assertEqual(client.call_count, 0, "the rule pass is free, so use it")


class TestModelRoute(unittest.TestCase):
    def test_the_catalogue_reaches_the_system_message(self):
        messages = build_router_messages(ROUTES, "hello")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        for route in ROUTES:
            self.assertIn(route.name, messages[0]["content"])
            self.assertIn(route.description, messages[0]["content"])

    def test_the_request_goes_last_and_alone(self):
        messages = build_router_messages(ROUTES, "please help me")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "please help me")

    def test_accepts_a_confident_label(self):
        client = MockClient([text(reply("tech", 0.88))])
        decision = model_route(client, ROUTES, "it stopped", fallback="general")
        self.assertEqual((decision.route, decision.reason), ("tech", "model"))
        self.assertAlmostEqual(decision.confidence, 0.88)

    def test_an_unknown_label_falls_back(self):
        client = MockClient([text(reply("legal", 0.99))])
        decision = model_route(client, ROUTES, "anything", fallback="general")
        self.assertEqual(decision.route, "general")
        self.assertEqual(
            decision.reason,
            "fallback:unknown-route",
            "a label you never offered is not a route, however confident it sounds",
        )

    def test_a_low_confidence_label_falls_back_and_keeps_the_number(self):
        client = MockClient([text(reply("billing", 0.41))])
        decision = model_route(
            client, ROUTES, "anything", fallback="general", threshold=0.6
        )
        self.assertEqual(decision.route, "general")
        self.assertEqual(decision.reason, "fallback:low-confidence")
        self.assertAlmostEqual(
            decision.confidence,
            0.41,
            msg="keep the reported number: it is what tells you where to put the floor",
        )

    def test_a_malformed_reply_falls_back(self):
        client = MockClient([text("Probably billing, I would say.")])
        decision = model_route(client, ROUTES, "anything", fallback="general")
        self.assertEqual(decision.route, "general")
        self.assertEqual(decision.reason, "fallback:malformed")

    def test_the_threshold_is_inclusive_at_its_own_value(self):
        client = MockClient([text(reply("tech", 0.6))])
        decision = model_route(
            client, ROUTES, "anything", fallback="general", threshold=0.6
        )
        self.assertEqual(decision.reason, "model", "the floor is a minimum, not a gap")

    def test_costs_exactly_one_call(self):
        client = MockClient([text(reply("tech", 0.9))])
        model_route(client, ROUTES, "anything", fallback="general")
        self.assertEqual(client.call_count, 1)

    def test_decide_falls_through_to_the_model_on_a_tie(self):
        client = MockClient([text(reply("tech", 0.9))])
        decision = Router(client, ROUTES, fallback="general").decide(
            "a refund because of a crash"
        )
        self.assertEqual(decision.route, "tech")
        self.assertEqual(client.call_count, 1)


class TestRouterConstruction(unittest.TestCase):
    def test_rejects_no_routes(self):
        with self.assertRaises(ValueError):
            Router(MockClient([]), [], fallback="general")

    def test_rejects_duplicate_names(self):
        with self.assertRaises(ValueError):
            Router(MockClient([]), [BILLING, BILLING], fallback="billing")

    def test_rejects_a_fallback_that_is_not_a_route(self):
        with self.assertRaises(ValueError):
            Router(MockClient([]), ROUTES, fallback="nobody")


class TestDispatch(unittest.TestCase):
    def test_runs_the_chosen_handler(self):
        result = router().dispatch("I need a refund")
        self.assertEqual(result.decision.route, "billing")
        self.assertEqual(result.output, "billing: I need a refund")

    def test_the_handler_receives_the_history(self):
        history = [
            {"role": "user", "content": "I have two invoices"},
            {"role": "assistant", "content": "Which one?"},
        ]
        result = router().dispatch("refund the second one", history)
        self.assertEqual(
            result.handoff.history,
            tuple(history),
            "a specialist given only the last message cannot resolve 'the second one'",
        )

    def test_history_defaults_to_empty(self):
        result = router().dispatch("I need a refund")
        self.assertEqual(result.handoff.history, ())

    def test_the_handoff_carries_the_reason(self):
        result = router(text(reply("general", 0.2))).dispatch("hello there")
        self.assertEqual(result.decision.route, "general")
        self.assertEqual(result.handoff.reason, "fallback:low-confidence")

    def test_a_fallback_still_runs_a_handler(self):
        result = router(text("not json at all")).dispatch("hello there")
        self.assertEqual(
            result.output,
            "general: hello there",
            "every request reaches some handler; routing to nothing is not an option",
        )

    def test_the_decision_is_the_one_the_handoff_was_built_from(self):
        result = router().dispatch("the app is broken")
        self.assertIsInstance(result.decision, Decision)
        self.assertEqual(result.handoff.reason, result.decision.reason)
        self.assertEqual(result.handoff.request, "the app is broken")


if __name__ == "__main__":
    unittest.main(verbosity=2)
