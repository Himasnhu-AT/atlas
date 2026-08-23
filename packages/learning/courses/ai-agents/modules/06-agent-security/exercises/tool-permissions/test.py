"""
Tests for: least privilege for tools.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    Order,
    Session,
    check_call,
    denial_observation,
    run_guarded,
    tools_for,
)


def session(**over) -> Session:
    base = Session(
        phase="gathering",
        approved=False,
        auto_refund_limit=100.0,
        orders={
            "A-1": Order("A-1", 40.0, "delivered"),
            "A-2": Order("A-2", 400.0, "delivered"),
            "A-3": Order("A-3", 40.0, "pending"),
        },
    )
    for key, value in over.items():
        setattr(base, key, value)
    return base


class TestToolsFor(unittest.TestCase):
    def test_gathering_gets_read_tools_only(self):
        self.assertEqual(tools_for(session()), ["lookup_order", "search_docs"])

    def test_acting_without_approval_is_still_read_only(self):
        tools = tools_for(session(phase="acting", approved=False))
        self.assertNotIn("refund_order", tools)

    def test_acting_and_approved_gets_the_write_tool(self):
        tools = tools_for(session(phase="acting", approved=True))
        self.assertIn("refund_order", tools)

    def test_is_sorted(self):
        tools = tools_for(session(phase="acting", approved=True))
        self.assertEqual(tools, sorted(tools))


class TestCheckCall(unittest.TestCase):
    def test_a_read_tool_is_fine_while_gathering(self):
        self.assertTrue(check_call("search_docs", {}, session()).allowed)

    def test_an_unavailable_tool_is_refused(self):
        decision = check_call("refund_order", {"order_id": "A-1"}, session())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "not available")

    def test_availability_is_checked_before_anything_else(self):
        # An unavailable tool must not leak whether some order exists.
        decision = check_call("refund_order", {"order_id": "NOPE"}, session())
        self.assertEqual(
            decision.reason,
            "not available",
            "a tool that was never offered should report that, not report on "
            "an order the caller was guessing at",
        )

    def test_an_allowed_refund_passes(self):
        s = session(phase="acting", approved=True)
        self.assertTrue(check_call("refund_order", {"order_id": "A-1"}, s).allowed)

    def test_a_missing_order_id_is_refused(self):
        s = session(phase="acting", approved=True)
        self.assertEqual(check_call("refund_order", {}, s).reason, "no order_id")

    def test_an_order_from_outside_the_session_is_refused(self):
        s = session(phase="acting", approved=True)
        decision = check_call("refund_order", {"order_id": "SOMEONE-ELSE"}, s)
        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reason,
            "not in this session",
            "the values the decision reads are values the attacker cannot write",
        )

    def test_an_undelivered_order_is_refused(self):
        s = session(phase="acting", approved=True)
        self.assertEqual(check_call("refund_order", {"order_id": "A-3"}, s).reason, "not delivered")

    def test_an_amount_over_the_limit_is_refused(self):
        s = session(phase="acting", approved=True)
        self.assertEqual(
            check_call("refund_order", {"order_id": "A-2"}, s).reason,
            "over the automatic limit",
        )

    def test_the_same_check_catches_the_model_simply_being_wrong(self):
        # Not an attack: a long context, two ids, and the wrong one chosen. This
        # is far more common than an injection and gets no press.
        s = session(phase="acting", approved=True)
        self.assertFalse(check_call("refund_order", {"order_id": "A-9"}, s).allowed)

    def test_a_reason_does_not_leak_policy(self):
        s = session(phase="acting", approved=True)
        for order_id in ["A-1", "A-2", "A-3", "NOPE"]:
            reason = check_call("refund_order", {"order_id": order_id}, s).reason
            self.assertNotIn(
                "100",
                reason,
                "the reason goes into the model's context, which the attacker "
                "can read: do not put the limit in it",
            )


class TestDenialObservation(unittest.TestCase):
    def test_is_a_tool_message_the_loop_can_carry_on_from(self):
        from solution import Decision

        message = denial_observation("refund_order", Decision(False, "not available"))
        self.assertEqual(message["role"], "tool")
        self.assertIn("tool_call_id", message)
        self.assertIn("refund_order", message["content"])
        self.assertIn("not available", message["content"])


class TestRunGuarded(unittest.TestCase):
    def test_the_injection_persuades_the_model_and_achieves_nothing(self):
        # The document from the previous exercise worked: the model asked for a
        # refund. The tool was not in the array, so there is nothing to run.
        calls = [
            {"name": "search_docs", "arguments": {"query": "error 402"}},
            {"name": "refund_order", "arguments": {"order_id": "A-1"}},
        ]
        result = run_guarded(calls, session())

        self.assertEqual(result["executed"], ["search_docs"])
        self.assertEqual(
            [d["name"] for d in result["denied"]],
            ["refund_order"],
            "the persuasion succeeded and produced nothing, which is what a "
            "control looks like",
        )

    def test_a_denial_does_not_stop_the_run(self):
        calls = [
            {"name": "refund_order", "arguments": {"order_id": "A-1"}},
            {"name": "lookup_order", "arguments": {"order_id": "A-1"}},
        ]
        result = run_guarded(calls, session())
        self.assertIn(
            "lookup_order",
            result["executed"],
            "stopping would make a refused call indistinguishable from a crash",
        )

    def test_produces_one_observation_per_denial(self):
        calls = [
            {"name": "refund_order", "arguments": {"order_id": "A-1"}},
            {"name": "refund_order", "arguments": {"order_id": "A-2"}},
        ]
        result = run_guarded(calls, session())
        self.assertEqual(len(result["observations"]), 2)
        self.assertTrue(all(o["role"] == "tool" for o in result["observations"]))

    def test_observations_have_distinct_call_ids(self):
        calls = [
            {"name": "refund_order", "arguments": {}},
            {"name": "refund_order", "arguments": {}},
        ]
        result = run_guarded(calls, session())
        ids = [o["tool_call_id"] for o in result["observations"]]
        self.assertEqual(len(set(ids)), 2, "two results answering one id is ambiguous")

    def test_an_approved_run_executes_the_refund(self):
        calls = [{"name": "refund_order", "arguments": {"order_id": "A-1"}}]
        result = run_guarded(calls, session(phase="acting", approved=True))
        self.assertEqual(result["executed"], ["refund_order"])
        self.assertEqual(result["denied"], [])

    def test_no_calls_is_not_an_error(self):
        result = run_guarded([], session())
        self.assertEqual(result, {"executed": [], "denied": [], "observations": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)
