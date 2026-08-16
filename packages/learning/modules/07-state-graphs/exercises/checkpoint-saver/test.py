"""
Tests for: checkpoints, resume, and time travel.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from mockllm import MockClient, text

from solution import (
    END,
    Channel,
    Checkpoint,
    InMemorySaver,
    StateGraph,
    append,
    fork,
    new_checkpoint_id,
    run_with_checkpoints,
)

#: How many times each node has been called, across every run in one test.
#: Cleared in setUp. A resumed run that re-executes finished work shows up here.
CALLS: dict = {}


def build_graph(client: MockClient | None = None, fail_b_until: int = 0) -> StateGraph:
    """
    a then b then c, each appending its name to `log`.

    `fail_b_until` makes b raise on its first N calls ever, counted across runs,
    which is how a crash halfway through a run is simulated.
    """
    graph = StateGraph([Channel("log", append, list)])

    def a(values):
        CALLS["a"] = CALLS.get("a", 0) + 1
        if client is not None:
            client.chat.completions.create(
                model="mock", messages=[{"role": "user", "content": "go"}]
            )
        return {"log": "a"}

    def b(values):
        CALLS["b"] = CALLS.get("b", 0) + 1
        if CALLS["b"] <= fail_b_until:
            raise RuntimeError("b fell over")
        return {"log": "b"}

    def c(values):
        CALLS["c"] = CALLS.get("c", 0) + 1
        return {"log": "c"}

    graph.add_node("a", a, subscribes=[])
    graph.add_node("b", b, subscribes=[])
    graph.add_node("c", c, subscribes=[])
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph.add_edge("c", END)
    graph.set_entry_point("a")
    return graph


class TestCheckpointIds(unittest.TestCase):
    def test_string_order_is_chronological_order(self):
        ids = [new_checkpoint_id(n) for n in (0, 1, 2, 9, 10, 11, 100)]
        self.assertEqual(
            ids,
            sorted(ids),
            "str(counter) puts '10' before '2'. Zero pad it, or history comes back "
            "in an order that is almost right",
        )

    def test_ids_are_fixed_width(self):
        self.assertEqual(len(new_checkpoint_id(0)), len(new_checkpoint_id(9999)))

    def test_ids_are_strings(self):
        self.assertIsInstance(new_checkpoint_id(3), str)


class TestSaverBasics(unittest.TestCase):
    def setUp(self):
        self.saver = InMemorySaver()
        self.checkpoint = Checkpoint(
            v=1,
            id=new_checkpoint_id(0),
            ts="2026-01-01T00:00:00+00:00",
            channel_values={"log": []},
            channel_versions={"log": 0},
            versions_seen={},
            updated_channels=[],
        )

    def test_put_returns_the_config_it_wrote(self):
        written = self.saver.put({"thread_id": "t"}, self.checkpoint)
        self.assertEqual(
            written,
            {"thread_id": "t", "checkpoint_id": new_checkpoint_id(0)},
            "put fills the id in, so the caller can chain it as the next parent",
        )

    def test_get_tuple_on_an_unknown_thread_is_none(self):
        self.assertIsNone(
            self.saver.get_tuple({"thread_id": "never-run"}),
            "a thread that has never run is the ordinary first call, not an error",
        )

    def test_get_tuple_on_an_unknown_id_is_none(self):
        self.saver.put({"thread_id": "t"}, self.checkpoint)
        self.assertIsNone(self.saver.get_tuple({"thread_id": "t", "checkpoint_id": "nope"}))

    def test_list_on_an_unknown_thread_is_empty(self):
        self.assertEqual(self.saver.list({"thread_id": "never-run"}), [])


class TestCheckpointWriting(unittest.TestCase):
    def setUp(self):
        CALLS.clear()
        self.saver = InMemorySaver()
        self.config = {"thread_id": "t1"}
        self.result = run_with_checkpoints(build_graph(), self.saver, self.config)

    def test_one_checkpoint_per_super_step(self):
        self.assertEqual(len(self.result.steps), 3)
        self.assertEqual(
            len(self.saver.list(self.config)),
            3,
            "the checkpoint goes in after every super-step, not once at the end",
        )

    def test_list_returns_newest_first(self):
        stored = self.saver.list(self.config)
        self.assertEqual(
            stored[0].checkpoint.channel_values["log"],
            ["a", "b", "c"],
            "newest first, which is the order anything showing history wants",
        )
        ids = [entry.checkpoint.id for entry in stored]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_list_respects_the_limit(self):
        self.assertEqual(len(self.saver.list(self.config, limit=2)), 2)

    def test_get_tuple_defaults_to_the_newest(self):
        found = self.saver.get_tuple(self.config)
        self.assertEqual(found.checkpoint.channel_values["log"], ["a", "b", "c"])

    def test_the_first_checkpoint_has_no_parent(self):
        oldest = self.saver.list(self.config)[-1]
        self.assertIsNone(oldest.parent_config)

    def test_each_checkpoint_names_the_one_before_it(self):
        newest, middle, oldest = self.saver.list(self.config)
        self.assertEqual(
            newest.parent_config,
            {"thread_id": "t1", "checkpoint_id": middle.checkpoint.id},
        )
        self.assertEqual(
            middle.parent_config,
            {"thread_id": "t1", "checkpoint_id": oldest.checkpoint.id},
        )

    def test_checkpoints_do_not_alias_the_live_state(self):
        oldest = self.saver.list(self.config)[-1]
        self.assertEqual(
            oldest.checkpoint.channel_values["log"],
            ["a"],
            "deep copy the values on the way in: values() hands back a new dict "
            "holding the same list, so without a copy every checkpoint in the "
            "thread shows the final state",
        )

    def test_updated_channels_match_what_the_step_wrote(self):
        for entry in self.saver.list(self.config):
            self.assertEqual(entry.checkpoint.updated_channels, ["log"])

    def test_the_format_version_is_recorded(self):
        self.assertEqual(self.saver.get_tuple(self.config).checkpoint.v, 1)

    def test_versions_seen_is_carried_too(self):
        newest = self.saver.get_tuple(self.config).checkpoint
        self.assertIn(
            "a",
            newest.versions_seen,
            "without versions_seen a resumed run cannot tell which nodes are done",
        )


class TestResume(unittest.TestCase):
    def setUp(self):
        CALLS.clear()
        self.saver = InMemorySaver()
        self.client = MockClient([text("ok")])
        self.config = {"thread_id": "crashy"}
        with self.assertRaises(RuntimeError):
            run_with_checkpoints(
                build_graph(self.client, fail_b_until=1), self.saver, self.config
            )

    def test_the_crash_keeps_the_step_that_finished(self):
        self.assertEqual(
            len(self.saver.list(self.config)),
            1,
            "a raised the flag before b fell over, so a's super-step is durable and "
            "b's was never written",
        )

    def test_resuming_completes_the_run(self):
        result = run_with_checkpoints(
            build_graph(self.client, fail_b_until=1), self.saver, self.config
        )
        self.assertEqual(result.values["log"], ["a", "b", "c"])

    def test_resuming_does_not_replay_finished_nodes(self):
        run_with_checkpoints(build_graph(self.client, fail_b_until=1), self.saver, self.config)
        self.assertEqual(
            CALLS["a"],
            1,
            "versions_seen came back from the checkpoint, so a is not eligible and "
            "does not run twice",
        )
        self.assertEqual(
            self.client.call_count,
            1,
            "replaying a node that called a model is the expensive version of the "
            "same bug",
        )

    def test_resuming_runs_the_node_that_failed(self):
        run_with_checkpoints(build_graph(self.client, fail_b_until=1), self.saver, self.config)
        self.assertEqual(CALLS["b"], 2, "b never completed, so b is still eligible")

    def test_the_resumed_run_reports_only_its_own_steps(self):
        result = run_with_checkpoints(
            build_graph(self.client, fail_b_until=1), self.saver, self.config
        )
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(
            len(self.saver.list(self.config)),
            3,
            "the thread now holds three checkpoints, with ids that keep going up",
        )


class TestTimeTravel(unittest.TestCase):
    def setUp(self):
        CALLS.clear()
        self.saver = InMemorySaver()
        self.config = {"thread_id": "t"}
        run_with_checkpoints(build_graph(), self.saver, self.config)
        self.oldest_id = self.saver.list(self.config)[-1].checkpoint.id

    def test_an_explicit_id_returns_that_state(self):
        found = self.saver.get_tuple({"thread_id": "t", "checkpoint_id": self.oldest_id})
        self.assertEqual(found.checkpoint.channel_values["log"], ["a"])

    def test_running_forward_from_it_reproduces_the_later_values(self):
        result = run_with_checkpoints(
            build_graph(), self.saver, {"thread_id": "t", "checkpoint_id": self.oldest_id}
        )
        self.assertEqual(result.values["log"], ["a", "b", "c"])
        self.assertEqual(len(result.steps), 2, "only b and c were left to run")

    def test_the_replay_appends_to_the_history(self):
        run_with_checkpoints(
            build_graph(), self.saver, {"thread_id": "t", "checkpoint_id": self.oldest_id}
        )
        self.assertEqual(
            len(self.saver.list(self.config)),
            5,
            "a replay writes new checkpoints rather than editing the old ones: the "
            "counter continues from what the thread already holds",
        )


class TestFork(unittest.TestCase):
    def setUp(self):
        CALLS.clear()
        self.saver = InMemorySaver()
        self.config = {"thread_id": "t"}
        run_with_checkpoints(build_graph(), self.saver, self.config)
        self.oldest_id = self.saver.list(self.config)[-1].checkpoint.id
        self.forked = fork(self.saver, self.config, self.oldest_id, "branch")

    def test_the_fork_starts_with_one_checkpoint(self):
        stored = self.saver.list({"thread_id": "branch"})
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].checkpoint.channel_values["log"], ["a"])

    def test_the_fork_points_back_at_where_it_came_from(self):
        stored = self.saver.list({"thread_id": "branch"})[0]
        self.assertEqual(
            stored.parent_config,
            {"thread_id": "t", "checkpoint_id": self.oldest_id},
            "parent_config across threads is what makes the history a tree",
        )

    def test_the_returned_config_runs(self):
        result = run_with_checkpoints(build_graph(), self.saver, self.forked)
        self.assertEqual(result.values["log"], ["a", "b", "c"])

    def test_the_original_thread_is_untouched(self):
        run_with_checkpoints(build_graph(), self.saver, self.forked)
        self.assertEqual(
            len(self.saver.list(self.config)),
            3,
            "running the fork must not write into the thread it branched from",
        )
        self.assertEqual(
            self.saver.list(self.config)[-1].checkpoint.channel_values["log"],
            ["a"],
            "and must not edit its values either: deep copy at the fork",
        )

    def test_the_forks_ids_start_from_the_beginning(self):
        stored = self.saver.list({"thread_id": "branch"})[0]
        self.assertEqual(stored.checkpoint.id, new_checkpoint_id(0))

    def test_two_threads_never_see_each_others_values(self):
        CALLS.clear()
        run_with_checkpoints(build_graph(), self.saver, {"thread_id": "x"}, inputs={"log": "x"})
        run_with_checkpoints(build_graph(), self.saver, {"thread_id": "y"}, inputs={"log": "y"})
        x_values = self.saver.get_tuple({"thread_id": "x"}).checkpoint.channel_values
        y_values = self.saver.get_tuple({"thread_id": "y"}).checkpoint.channel_values
        self.assertEqual(x_values["log"], ["x", "a", "b", "c"])
        self.assertEqual(y_values["log"], ["y", "a", "b", "c"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
