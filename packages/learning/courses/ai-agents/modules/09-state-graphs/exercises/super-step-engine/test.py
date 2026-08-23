"""
Tests for: the super step.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    END,
    START,
    Channel,
    StateGraph,
    SuperStepLimit,
    add_int,
    append,
    last_value,
)


def linear_graph() -> StateGraph:
    """a then b then c, one after another, ending at END."""
    graph = StateGraph([Channel("log", append, list)])
    graph.add_node("a", lambda values: {"log": "a"}, subscribes=[])
    graph.add_node("b", lambda values: {"log": "b"}, subscribes=[])
    graph.add_node("c", lambda values: {"log": "c"}, subscribes=[])
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", END)
    graph.set_entry_point("a")
    return graph


def fan_graph() -> StateGraph:
    """source, then left and right together, then sink over both their writes."""
    graph = StateGraph(
        [
            Channel("counter", add_int, lambda: 0),
            Channel("seen", append, list),
            Channel("summary", last_value, lambda: ""),
        ]
    )
    graph.add_node("source", lambda values: {"counter": 10}, subscribes=[])
    graph.add_node(
        "left",
        lambda values: {"seen": f"left:{values['counter']}", "counter": 1},
        subscribes=[],
    )
    graph.add_node(
        "right",
        lambda values: {"seen": f"right:{values['counter']}", "counter": 1},
        subscribes=[],
    )
    graph.add_node(
        "sink", lambda values: {"summary": "|".join(values["seen"])}, subscribes=["seen"]
    )
    graph.add_edge("source", "left")
    graph.add_edge("source", "right")
    graph.set_entry_point("source")
    return graph


class TestLinearRun(unittest.TestCase):
    def test_one_node_per_super_step_in_order(self):
        result = linear_graph().run({})
        self.assertEqual(
            [step.nodes for step in result.steps],
            [["a"], ["b"], ["c"]],
            "each node is woken by the edge into it, so each gets its own super-step",
        )

    def test_step_indices_start_at_zero(self):
        result = linear_graph().run({})
        self.assertEqual([step.index for step in result.steps], [0, 1, 2])

    def test_produces_the_expected_values(self):
        result = linear_graph().run({})
        self.assertEqual(result.values["log"], ["a", "b", "c"])

    def test_an_edge_to_end_finishes_the_run(self):
        self.assertTrue(linear_graph().run({}).finished)

    def test_an_edge_writes_the_targets_trigger_channel(self):
        result = linear_graph().run({})
        self.assertIn(
            "to:b",
            result.values,
            "an edge into b is a write to a channel named 'to:b' that b subscribes to",
        )

    def test_start_names_the_entry_point(self):
        graph = StateGraph([Channel("log", append, list)])
        graph.add_node("only", lambda values: {"log": "only"}, subscribes=[])
        graph.add_edge(START, "only")
        self.assertEqual(graph.run({}).values["log"], ["only"])

    def test_updated_lists_what_the_nodes_wrote(self):
        result = linear_graph().run({})
        self.assertEqual(
            [step.updated for step in result.steps],
            [["log"], ["log"], ["log"]],
            "updated is the channels the nodes' own updates touched",
        )


class TestInputs(unittest.TestCase):
    def test_inputs_go_through_the_reducer(self):
        graph = StateGraph([Channel("count", add_int, lambda: 0)])
        graph.add_node("bump", lambda values: {"count": 1}, subscribes=[])
        graph.set_entry_point("bump")
        result = graph.run({"count": 10})
        self.assertEqual(
            result.values["count"],
            11,
            "seeding is an ordinary write: add_int adds rather than overwrites",
        )

    def test_a_node_returning_none_writes_nothing(self):
        graph = StateGraph([Channel("log", append, list)])
        graph.add_node("quiet", lambda values: None, subscribes=[])
        graph.set_entry_point("quiet")
        result = graph.run({})
        self.assertEqual(result.values["log"], [])
        self.assertEqual(result.steps[0].updated, [])

    def test_a_run_with_nothing_left_to_do_is_not_finished(self):
        graph = StateGraph([Channel("log", append, list)])
        graph.add_node("only", lambda values: {"log": "x"}, subscribes=[])
        graph.set_entry_point("only")
        result = graph.run({})
        self.assertFalse(
            result.finished,
            "running out of eligible nodes is quiescence, not END, and telling them "
            "apart is how you notice a graph that stopped early",
        )


class TestFanOutAndFanIn(unittest.TestCase):
    def setUp(self):
        self.result = fan_graph().run({})

    def test_both_branches_run_in_one_super_step(self):
        self.assertEqual(self.result.steps[1].nodes, ["left", "right"])

    def test_both_branches_read_the_pre_step_value(self):
        self.assertEqual(
            self.result.values["seen"][:2],
            ["left:10", "right:10"],
            "both nodes get the snapshot taken before the step, so neither can see "
            "the other's write to counter",
        )

    def test_writes_merge_in_node_name_order(self):
        self.assertEqual(self.result.values["seen"][0], "left:10")

    def test_both_writes_land(self):
        self.assertEqual(
            self.result.values["counter"],
            12,
            "10 from source, then 1 from each branch: every update in the step is "
            "merged, not just the last one",
        )

    def test_the_fan_in_node_runs_in_the_next_super_step(self):
        self.assertEqual(self.result.steps[2].nodes, ["sink"])

    def test_the_fan_in_node_sees_both_branches(self):
        self.assertEqual(self.result.values["summary"], "left:10|right:10")

    def test_the_step_reports_every_channel_it_wrote(self):
        self.assertEqual(self.result.steps[1].updated, ["counter", "seen"])


class TestConditionalEdges(unittest.TestCase):
    def build(self, choice: str) -> StateGraph:
        graph = StateGraph(
            [Channel("choice", last_value, lambda: ""), Channel("log", append, list)]
        )
        graph.add_node(
            "source", lambda values: {"choice": choice, "log": "source"}, subscribes=[]
        )
        graph.add_node("b", lambda values: {"log": "b"}, subscribes=[])
        graph.add_node("c", lambda values: {"log": "c"}, subscribes=[])
        graph.add_conditional_edges("source", lambda values: values["choice"])
        graph.add_edge("b", END)
        graph.add_edge("c", END)
        graph.set_entry_point("source")
        return graph

    def test_only_the_chosen_branch_runs(self):
        result = self.build("b").run({})
        self.assertEqual(
            result.values["log"],
            ["source", "b"],
            "the router picked b, so c never ran at all",
        )

    def test_the_router_reads_the_merged_values(self):
        result = self.build("c").run({})
        self.assertEqual(
            result.values["log"],
            ["source", "c"],
            "the router runs after the step's writes are merged, so it can read the "
            "channel the source node just set",
        )

    def test_routing_to_end_finishes_the_run(self):
        graph = self.build(END)
        result = graph.run({})
        self.assertTrue(result.finished)
        self.assertEqual(result.values["log"], ["source"])

    def test_an_unknown_route_is_an_error(self):
        with self.assertRaises(ValueError):
            self.build("nowhere").run({})


class TestSubscriptions(unittest.TestCase):
    def build(self, subscribes: list[str], client: MockClient) -> StateGraph:
        def talker(values):
            client.chat.completions.create(
                model="mock", messages=[{"role": "user", "content": "go"}]
            )
            return {"answer": "ok"}

        graph = StateGraph(
            [Channel("noise", add_int, lambda: 0), Channel("answer", last_value, lambda: "")]
        )
        graph.add_node("talker", talker, subscribes=subscribes)
        graph.add_node("noisemaker", lambda values: {"noise": 1}, subscribes=[])
        graph.add_edge("talker", "noisemaker")
        graph.set_entry_point("talker")
        return graph

    def test_an_unsubscribed_channel_does_not_wake_a_node(self):
        client = MockClient([text("ok")])
        result = self.build([], client).run({})
        self.assertEqual(
            client.call_count,
            1,
            "talker does not subscribe to 'noise', so noisemaker changing it is none "
            "of talker's business",
        )
        self.assertEqual([step.nodes for step in result.steps], [["talker"], ["noisemaker"]])

    def test_subscribing_to_it_wakes_the_node_again(self):
        client = MockClient([text("ok")], strict=False)
        graph = self.build(["noise"], client)
        with self.assertRaises(SuperStepLimit):
            graph.run({}, max_steps=4)
        self.assertEqual(
            client.call_count,
            2,
            "the same graph with one extra subscription is now a cycle: subscriptions "
            "are the whole of the wiring",
        )


class TestLimits(unittest.TestCase):
    def test_a_cycle_raises_super_step_limit(self):
        graph = StateGraph([Channel("log", append, list)])
        graph.add_node("ping", lambda values: {"log": "ping"}, subscribes=[])
        graph.add_node("pong", lambda values: {"log": "pong"}, subscribes=[])
        graph.add_edge("ping", "pong")
        graph.add_edge("pong", "ping")
        graph.set_entry_point("ping")

        with self.assertRaises(SuperStepLimit) as caught:
            graph.run({}, max_steps=5)
        self.assertEqual(
            len(caught.exception.steps),
            5,
            "attach the records collected before giving up: the shape of a runaway "
            "graph is the only useful thing about it",
        )


class TestConstruction(unittest.TestCase):
    def test_rejects_a_duplicate_node_name(self):
        graph = StateGraph([])
        graph.add_node("a", lambda values: None, subscribes=[])
        with self.assertRaises(ValueError):
            graph.add_node("a", lambda values: None, subscribes=[])

    def test_rejects_a_subscription_to_an_unknown_channel(self):
        graph = StateGraph([Channel("log", append, list)])
        with self.assertRaises(ValueError):
            graph.add_node("a", lambda values: None, subscribes=["lgo"])

    def test_rejects_an_edge_to_an_unknown_node(self):
        graph = StateGraph([])
        graph.add_node("a", lambda values: None, subscribes=[])
        with self.assertRaises(ValueError):
            graph.add_edge("a", "ghost")

    def test_rejects_static_and_conditional_edges_on_one_node(self):
        graph = StateGraph([])
        graph.add_node("a", lambda values: None, subscribes=[])
        graph.add_node("b", lambda values: None, subscribes=[])
        graph.add_edge("a", "b")
        with self.assertRaises(ValueError):
            graph.add_conditional_edges("a", lambda values: "b")

    def test_rejects_a_run_with_no_entry_point(self):
        graph = StateGraph([])
        graph.add_node("a", lambda values: None, subscribes=[])
        with self.assertRaises(ValueError):
            graph.run({})


if __name__ == "__main__":
    unittest.main(verbosity=2)
