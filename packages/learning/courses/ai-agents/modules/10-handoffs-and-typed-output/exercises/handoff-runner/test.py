"""
Tests for: handoffs are tool calls.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, tool_call, tool_calls

from solution import (
    Agent,
    MaxTurnsExceeded,
    RunResult,
    UnknownHandoff,
    dispatch,
    handoff_tool_name,
    run,
    tool_schemas,
)


def issue_refund(order_id: str) -> str:
    """Refund an order in full."""
    return f"refunded {order_id}"


def order_status(order_id: str, verbose: str = "no") -> str:
    """Look up the status of an order."""
    return f"order {order_id}: shipped"


def build_agents() -> tuple[Agent, Agent, Agent]:
    """triage hands to billing, billing hands to refunds. Fresh every test."""
    refunds = Agent(
        name="refunds",
        instructions="Issue refunds and confirm the amount.",
        tools=[issue_refund],
    )
    billing = Agent(
        name="billing",
        instructions="Answer billing questions.",
        tools=[order_status],
        handoffs=[refunds],
    )
    triage = Agent(
        name="triage",
        instructions="Work out who should handle this.",
        handoffs=[billing],
    )
    return triage, billing, refunds


def schema_names(schemas: list[dict]) -> list[str]:
    return [schema["function"]["name"] for schema in schemas]


class TestHandoffToolName(unittest.TestCase):
    def test_prefixes_and_lowercases(self):
        self.assertEqual(
            handoff_tool_name(Agent(name="Billing", instructions="")),
            "transfer_to_billing",
        )

    def test_spaces_and_hyphens_become_underscores(self):
        self.assertEqual(
            handoff_tool_name(Agent(name="Refund Desk", instructions="")),
            "transfer_to_refund_desk",
            "spaces have to go: a provider rejects a tool name containing one",
        )
        self.assertEqual(
            handoff_tool_name(Agent(name="on-call", instructions="")),
            "transfer_to_on_call",
        )


class TestToolSchemas(unittest.TestCase):
    def test_describes_a_real_tool_from_its_signature(self):
        _, billing, _ = build_agents()
        schema = tool_schemas(billing)[0]["function"]
        self.assertEqual(schema["name"], "order_status")
        self.assertEqual(schema["description"], "Look up the status of an order.")
        self.assertEqual(
            schema["parameters"]["properties"],
            {"order_id": {"type": "string"}, "verbose": {"type": "string"}},
        )

    def test_only_parameters_without_defaults_are_required(self):
        _, billing, _ = build_agents()
        schema = tool_schemas(billing)[0]["function"]
        self.assertEqual(
            schema["parameters"]["required"],
            ["order_id"],
            "verbose has a default, so the model may leave it out",
        )

    def test_one_synthetic_tool_per_handoff_target(self):
        triage, _, _ = build_agents()
        self.assertIn("transfer_to_billing", schema_names(tool_schemas(triage)))

    def test_handoff_schema_takes_no_arguments(self):
        triage, _, _ = build_agents()
        handoff = tool_schemas(triage)[-1]["function"]
        self.assertEqual(handoff["parameters"]["properties"], {})
        self.assertEqual(
            handoff["description"],
            "Hand off to billing. Answer billing questions.",
            "the target's own instructions are the only description the model gets",
        )

    def test_real_tools_come_before_handoffs(self):
        _, billing, _ = build_agents()
        self.assertEqual(schema_names(tool_schemas(billing)), ["order_status", "transfer_to_refunds"])

    def test_an_agent_only_advertises_its_own_handoffs(self):
        _, billing, _ = build_agents()
        self.assertNotIn(
            "transfer_to_billing",
            schema_names(tool_schemas(billing)),
            "billing cannot transfer to itself: handoffs point one way, from the "
            "agent that declares them",
        )


class TestDispatch(unittest.TestCase):
    def test_runs_the_tool_and_stringifies_the_result(self):
        _, _, refunds = build_agents()
        self.assertEqual(dispatch(refunds, "issue_refund", '{"order_id": "A-1"}'), "refunded A-1")

    def test_unknown_tool_raises(self):
        _, _, refunds = build_agents()
        with self.assertRaises(KeyError):
            dispatch(refunds, "order_status", "{}")


class TestHandoffs(unittest.TestCase):
    def test_a_transfer_reassigns_the_agent(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])

        result = run(triage, "I was charged twice", client)

        self.assertIsInstance(result, RunResult)
        self.assertEqual(result.last_agent, "billing")
        self.assertEqual(result.final_output, "Refunded.")
        self.assertEqual(result.handoffs, [("triage", "billing")])

    def test_history_survives_the_transfer(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])
        run(triage, "I was charged twice", client)

        sent = client.requests[1]["messages"]
        contents = [message.get("content") for message in sent]
        self.assertIn(
            "I was charged twice",
            contents,
            "the new agent inherits the conversation, it does not start a new one",
        )
        self.assertTrue(
            any(message["role"] == "tool" for message in sent),
            "the transfer call still needs an answer, or the request is malformed",
        )

    def test_the_transfer_result_is_keyed_to_the_call(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])
        run(triage, "help", client)

        sent = client.requests[1]["messages"]
        assistant = next(m for m in sent if m["role"] == "assistant")
        answer = next(m for m in sent if m["role"] == "tool")
        self.assertEqual(answer["tool_call_id"], assistant["tool_calls"][0]["id"])

    def test_the_new_agent_brings_its_own_prompt(self):
        triage, billing, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])
        run(triage, "help", client)

        first = client.requests[1]["messages"][0]
        self.assertEqual(first["role"], "system")
        self.assertEqual(
            first["content"],
            billing.instructions,
            "after a handoff the system message is the new agent's instructions",
        )

    def test_the_new_agent_brings_its_own_tools(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])
        run(triage, "help", client)

        offered = schema_names(client.requests[1]["tools"])
        self.assertNotIn(
            "transfer_to_billing",
            offered,
            "the tools list belongs to the current agent, not to the run",
        )
        self.assertEqual(offered, ["order_status", "transfer_to_refunds"])

    def test_two_hops_are_recorded_in_order(self):
        triage, _, _ = build_agents()
        client = MockClient(
            [
                tool_call("transfer_to_billing", {}),
                tool_call("transfer_to_refunds", {}),
                text("Refunded in full."),
            ]
        )

        result = run(triage, "refund me", client)

        self.assertEqual(result.handoffs, [("triage", "billing"), ("billing", "refunds")])
        self.assertEqual(result.last_agent, "refunds")
        self.assertEqual(result.turns, 3)

    def test_an_unreachable_target_raises(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_nobody", {})])

        with self.assertRaises(UnknownHandoff):
            run(triage, "help", client)


class TestOrdinaryTools(unittest.TestCase):
    def test_a_tool_result_goes_back_with_its_call_id(self):
        _, billing, _ = build_agents()
        client = MockClient(
            [tool_call("order_status", {"order_id": "A-1"}), text("It shipped.")]
        )
        run(billing, "where is A-1?", client)

        sent = client.requests[1]["messages"]
        assistant = next(m for m in sent if m["role"] == "assistant")
        answer = next(m for m in sent if m["role"] == "tool")
        self.assertEqual(answer["content"], "order A-1: shipped")
        self.assertEqual(answer["tool_call_id"], assistant["tool_calls"][0]["id"])

    def test_every_call_in_a_batch_is_answered(self):
        _, billing, _ = build_agents()
        client = MockClient(
            [
                tool_calls(
                    [
                        ("order_status", {"order_id": "A-1"}),
                        ("order_status", {"order_id": "A-2"}),
                    ]
                ),
                text("Both shipped."),
            ]
        )
        run(billing, "status of both?", client)

        sent = client.requests[1]["messages"]
        answered = [m["tool_call_id"] for m in sent if m["role"] == "tool"]
        requested = [
            call["id"] for m in sent if m["role"] == "assistant" for call in m["tool_calls"]
        ]
        self.assertEqual(requested, answered, "an unanswered call makes the request invalid")


class TestRunShape(unittest.TestCase):
    def test_an_answer_with_no_tools_ends_the_run(self):
        triage, _, _ = build_agents()
        client = MockClient([text("You want support at support@example.com.")])

        result = run(triage, "who do I email?", client)

        self.assertEqual(result.last_agent, "triage")
        self.assertEqual(result.handoffs, [])
        self.assertEqual(result.turns, 1)
        self.assertEqual(client.call_count, 1)

    def test_the_history_holds_no_system_message(self):
        triage, _, _ = build_agents()
        client = MockClient([tool_call("transfer_to_billing", {}), text("Refunded.")])

        result = run(triage, "help", client)

        self.assertNotIn(
            "system",
            [message["role"] for message in result.messages],
            "the system prompt changes with the agent, so it is built per request",
        )

    def test_running_out_of_turns_raises(self):
        triage, _, _ = build_agents()
        client = MockClient(
            [
                tool_call("transfer_to_billing", {}),
                tool_call("order_status", {"order_id": "A-1"}),
            ],
            strict=False,
        )

        with self.assertRaises(MaxTurnsExceeded):
            run(triage, "loop", client, max_turns=3)
        self.assertEqual(client.call_count, 3, "max_turns counts model calls")

    def test_a_budget_below_one_is_rejected(self):
        triage, _, _ = build_agents()
        with self.assertRaises(ValueError):
            run(triage, "help", MockClient([text("hi")]), max_turns=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
