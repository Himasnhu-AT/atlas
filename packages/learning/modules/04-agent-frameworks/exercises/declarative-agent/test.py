"""
Tests for: compiling a spec into an agent.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text, tool_call

from solution import (
    AgentSpec,
    SpecError,
    ToolRegistry,
    build_agent,
    diff_specs,
    spec_from_dict,
    validate_spec,
)


def refund(order_id: str = "") -> str:
    """Refund an order."""
    return f"refunded {order_id}"


def lookup(order_id: str = "") -> str:
    """Look up an order."""
    return f"order {order_id} shipped"


def escalate(reason: str = "") -> str:
    """Hand the conversation to a person."""
    return f"escalated: {reason}"


def registry() -> ToolRegistry:
    return ToolRegistry([refund, lookup, escalate])


TRIAGE = {
    "name": "triage",
    "system": "Work out what the customer needs.",
    "tools": ["lookup", "escalate"],
    "max_steps": 4,
}


class TestSpecFromDict(unittest.TestCase):
    def test_reads_a_full_spec(self):
        spec = spec_from_dict(TRIAGE)
        self.assertEqual(spec.name, "triage")
        self.assertEqual(spec.max_steps, 4)
        self.assertEqual(
            spec.tools, ("lookup", "escalate"), "tools become a tuple, in file order"
        )

    def test_fills_in_the_defaults(self):
        spec = spec_from_dict({"name": "minimal", "system": "Be brief."})
        self.assertEqual(spec.tools, ())
        self.assertEqual(spec.max_steps, 6)

    def test_names_a_missing_key(self):
        with self.assertRaises(SpecError) as caught:
            spec_from_dict({"name": "no prompt"})
        self.assertIn("system", str(caught.exception))

    def test_rejects_an_unknown_key(self):
        with self.assertRaises(SpecError) as caught:
            spec_from_dict({"name": "typo", "prompt": "Be brief."})
        self.assertIn(
            "prompt",
            str(caught.exception),
            "an ignored key silently produces an agent with no instructions",
        )

    def test_rejects_a_wrongly_typed_tools_list(self):
        with self.assertRaises(SpecError):
            spec_from_dict({"name": "n", "system": "s", "tools": "lookup"})

    def test_rejects_a_boolean_budget(self):
        with self.assertRaises(SpecError):
            spec_from_dict({"name": "n", "system": "s", "max_steps": True})

    def test_rejects_something_that_is_not_a_mapping(self):
        with self.assertRaises(SpecError):
            spec_from_dict(["name", "triage"])


class TestValidateSpec(unittest.TestCase):
    def test_a_good_spec_passes(self):
        self.assertIsNone(validate_spec(spec_from_dict(TRIAGE), registry()))

    def test_names_an_unknown_tool(self):
        spec = AgentSpec(name="billing", system="Help.", tools=("teleport",))
        with self.assertRaises(SpecError) as caught:
            validate_spec(spec, registry())
        self.assertIn("teleport", str(caught.exception))

    def test_suggests_a_close_name(self):
        spec = AgentSpec(name="billing", system="Help.", tools=("refunds",))
        with self.assertRaises(SpecError) as caught:
            validate_spec(spec, registry())
        # Quoted, so the echoed 'refunds' cannot satisfy this on its own: the
        # only way "'refund'" appears is if difflib actually suggested it.
        self.assertIn(
            "'refund'",
            str(caught.exception),
            "name the near miss the registry does have, not just the one it does not",
        )

    def test_rejects_a_duplicate_tool(self):
        spec = AgentSpec(name="billing", system="Help.", tools=("refund", "refund"))
        with self.assertRaises(SpecError):
            validate_spec(spec, registry())

    def test_rejects_a_blank_prompt(self):
        with self.assertRaises(SpecError):
            validate_spec(AgentSpec(name="billing", system="   "), registry())

    def test_rejects_a_budget_outside_the_ceiling(self):
        with self.assertRaises(SpecError):
            validate_spec(AgentSpec(name="b", system="Help.", max_steps=0), registry())
        with self.assertRaises(SpecError):
            validate_spec(AgentSpec(name="b", system="Help.", max_steps=5000), registry())


class TestBuildAgent(unittest.TestCase):
    def test_the_agent_runs(self):
        client = MockClient([tool_call("lookup", {"order_id": "A-1"}), text("It shipped.")])
        agent = build_agent(spec_from_dict(TRIAGE), registry(), client)

        self.assertEqual(agent.run("where is A-1?"), "It shipped.")
        self.assertEqual(agent.name, "triage")
        self.assertEqual(agent.max_steps, 4)
        self.assertEqual(client.requests[0]["messages"][0]["content"], TRIAGE["system"])

    def test_the_agent_sees_only_the_tools_it_named(self):
        agent = build_agent(spec_from_dict(TRIAGE), registry(), MockClient([text("ok")]))
        offered = [schema["function"]["name"] for schema in agent.registry.schemas]

        self.assertEqual(
            offered,
            ["lookup", "escalate"],
            "spec order, and refund is not on the list at all",
        )

    def test_a_bad_spec_fails_before_any_model_call(self):
        client = MockClient([text("never reached")])
        spec = AgentSpec(name="billing", system="Help.", tools=("teleport",))

        with self.assertRaises(SpecError):
            build_agent(spec, registry(), client)

        self.assertEqual(
            client.call_count,
            0,
            "a spec that cannot run must cost an exception, not a model call",
        )

    def test_one_registry_builds_several_agents(self):
        shared = registry()
        billing = build_agent(
            AgentSpec("billing", "Money questions only.", ("refund", "lookup")),
            shared,
            MockClient([text("refunded")]),
        )
        support = build_agent(
            AgentSpec("support", "Everything else.", ("escalate",)),
            shared,
            MockClient([text("escalated")]),
        )

        self.assertEqual(billing.registry.names, ["refund", "lookup"])
        self.assertEqual(support.registry.names, ["escalate"])
        self.assertEqual(shared.names, ["refund", "lookup", "escalate"], "unchanged")


class TestDiffSpecs(unittest.TestCase):
    def base(self) -> AgentSpec:
        return AgentSpec("triage", "Work it out.", ("lookup", "escalate"), 4)

    def test_identical_specs_differ_by_nothing(self):
        self.assertEqual(diff_specs(self.base(), self.base()), [])

    def test_reports_a_renamed_agent(self):
        changed = AgentSpec("router", "Work it out.", ("lookup", "escalate"), 4)
        self.assertEqual(diff_specs(self.base(), changed), ["name: 'triage' -> 'router'"])

    def test_reports_added_and_removed_tools(self):
        changed = AgentSpec("triage", "Work it out.", ("lookup", "refund"), 4)
        self.assertEqual(
            diff_specs(self.base(), changed),
            ["tools added: refund", "tools removed: escalate"],
        )

    def test_reports_a_reorder(self):
        changed = AgentSpec("triage", "Work it out.", ("escalate", "lookup"), 4)
        self.assertEqual(
            diff_specs(self.base(), changed),
            ["tools reordered"],
            "order is the order the model sees the tools in",
        )

    def test_the_prompt_gets_one_word(self):
        changed = AgentSpec("triage", "Work it out carefully.", ("lookup", "escalate"), 4)
        self.assertEqual(diff_specs(self.base(), changed), ["system: changed"])

    def test_lines_come_out_in_a_fixed_order(self):
        changed = AgentSpec("router", "Different.", ("lookup",), 8)
        self.assertEqual(
            diff_specs(self.base(), changed),
            [
                "name: 'triage' -> 'router'",
                "system: changed",
                "tools removed: escalate",
                "max_steps: 4 -> 8",
            ],
            "a diff that reorders itself is a diff nobody can review",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
