"""
Tests for: channels and reducers.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    Channel,
    ChannelState,
    UnknownChannel,
    add_int,
    append,
    eligible_nodes,
    last_value,
    merge_dicts,
    mark_seen,
)


def build_channels() -> list[Channel]:
    """A state with one channel per reducer."""
    return [
        Channel("answer", last_value, lambda: ""),
        Channel("notes", append, list),
        Channel("facts", merge_dicts, dict),
        Channel("tokens", add_int, lambda: 0),
    ]


class TestReducers(unittest.TestCase):
    def test_last_value_overwrites(self):
        self.assertEqual(last_value("old", "new"), "new")

    def test_append_returns_a_new_list(self):
        current = ["a"]
        result = append(current, "b")
        self.assertEqual(result, ["a", "b"])
        self.assertEqual(current, ["a"], "append must not mutate the current value")

    def test_append_extends_with_a_list_update(self):
        self.assertEqual(
            append(["a"], ["b", "c"]),
            ["a", "b", "c"],
            "a list update contributes its items, it does not nest",
        )

    def test_merge_dicts_keeps_untouched_keys(self):
        result = merge_dicts({"a": 1, "b": 2}, {"b": 3})
        self.assertEqual(result, {"a": 1, "b": 3})

    def test_add_int_sums(self):
        self.assertEqual(add_int(4, 6), 10)


class TestChannelStateDefaults(unittest.TestCase):
    def test_starts_at_the_defaults(self):
        state = ChannelState(build_channels())
        self.assertEqual(
            state.values(),
            {"answer": "", "notes": [], "facts": {}, "tokens": 0},
        )

    def test_every_version_starts_at_zero(self):
        state = ChannelState(build_channels())
        self.assertEqual(set(state.versions().values()), {0})

    def test_each_state_gets_its_own_default(self):
        channels = build_channels()
        first = ChannelState(channels)
        second = ChannelState(channels)
        self.assertIsNot(
            first.values()["notes"],
            second.values()["notes"],
            "call default() once per ChannelState, not once per Channel: sharing "
            "the object is the mutable-default bug in a new hat",
        )
        first.apply({"notes": "a"})
        self.assertEqual(
            second.values()["notes"], [], "two states must not share a channel value"
        )

    def test_values_returns_a_copy(self):
        state = ChannelState(build_channels())
        borrowed = state.values()
        borrowed["answer"] = "tampered"
        self.assertEqual(
            state.values()["answer"], "", "values() should hand back a new dict"
        )


class TestApply(unittest.TestCase):
    def setUp(self):
        self.state = ChannelState(build_channels())

    def test_returns_only_the_touched_channels(self):
        self.assertEqual(self.state.apply({"notes": "a"}), ["notes"])

    def test_returns_names_sorted(self):
        touched = self.state.apply({"tokens": 3, "answer": "x", "notes": "n"})
        self.assertEqual(touched, ["answer", "notes", "tokens"])

    def test_leaves_other_versions_untouched(self):
        self.state.apply({"notes": "a"})
        versions = self.state.versions()
        self.assertEqual(versions["notes"], 1)
        self.assertEqual(versions["answer"], 0, "a write to one channel is not a write to all")
        self.assertEqual(versions["tokens"], 0)

    def test_an_identical_write_still_bumps_the_version(self):
        self.state.apply({"answer": "same"})
        self.state.apply({"answer": "same"})
        self.assertEqual(
            self.state.versions()["answer"],
            2,
            "the version counts writes, not changes: the scheduler needs to know a "
            "node produced something, even when the value happens to match",
        )

    def test_append_accumulates_in_call_order(self):
        self.state.apply({"notes": "first"})
        self.state.apply({"notes": "second"})
        self.assertEqual(self.state.values()["notes"], ["first", "second"])

    def test_add_int_accumulates(self):
        self.state.apply({"tokens": 40})
        self.state.apply({"tokens": 2})
        self.assertEqual(self.state.values()["tokens"], 42)

    def test_last_value_overwrites_through_apply(self):
        self.state.apply({"answer": "draft"})
        self.state.apply({"answer": "final"})
        self.assertEqual(self.state.values()["answer"], "final")

    def test_merge_dicts_through_apply(self):
        self.state.apply({"facts": {"city": "Paris", "population": 2}})
        self.state.apply({"facts": {"population": 3}})
        self.assertEqual(self.state.values()["facts"], {"city": "Paris", "population": 3})

    def test_a_batch_writes_every_named_channel(self):
        self.state.apply({"answer": "a", "tokens": 5})
        self.assertEqual(self.state.values()["answer"], "a")
        self.assertEqual(self.state.values()["tokens"], 5)

    def test_unknown_channel_raises(self):
        with self.assertRaises(UnknownChannel):
            self.state.apply({"nots": "typo"})

    def test_unknown_channel_applies_none_of_the_batch(self):
        with self.assertRaises(UnknownChannel):
            self.state.apply({"notes": "good", "nots": "typo"})
        self.assertEqual(
            self.state.values()["notes"],
            [],
            "apply is all or nothing: validate every key before writing any of them",
        )
        self.assertEqual(self.state.versions()["notes"], 0)


class TestEligibleNodes(unittest.TestCase):
    def setUp(self):
        self.subscriptions = {"writer": ["answer"], "critic": ["notes"], "counter": ["tokens"]}

    def test_nothing_is_eligible_when_nothing_has_moved(self):
        versions = {"answer": 0, "notes": 0, "tokens": 0}
        self.assertEqual(
            eligible_nodes(self.subscriptions, versions, {}),
            [],
            "a channel at version 0 that nobody has seen is not work: compare with "
            "strictly greater than, not greater than or equal",
        )

    def test_everything_is_eligible_on_a_freshly_seeded_state(self):
        versions = {"answer": 1, "notes": 1, "tokens": 1}
        self.assertEqual(
            eligible_nodes(self.subscriptions, versions, {}),
            ["counter", "critic", "writer"],
            "an empty seen map means the node has read nothing yet",
        )

    def test_returns_only_the_node_whose_channel_moved(self):
        versions = {"answer": 2, "notes": 1, "tokens": 1}
        seen = {
            "writer": {"answer": 1},
            "critic": {"notes": 1},
            "counter": {"tokens": 1},
        }
        self.assertEqual(eligible_nodes(self.subscriptions, versions, seen), ["writer"])

    def test_ignores_a_node_subscribed_only_to_unchanged_channels(self):
        subscriptions = {"quiet": ["answer"], "loud": ["notes", "tokens"]}
        versions = {"answer": 1, "notes": 1, "tokens": 4}
        seen = {"quiet": {"answer": 1}, "loud": {"notes": 1, "tokens": 1}}
        self.assertEqual(eligible_nodes(subscriptions, versions, seen), ["loud"])

    def test_nothing_is_eligible_when_every_node_has_seen_every_version(self):
        versions = {"answer": 3, "notes": 3, "tokens": 3}
        seen = {
            "writer": {"answer": 3},
            "critic": {"notes": 3},
            "counter": {"tokens": 3},
        }
        self.assertEqual(eligible_nodes(self.subscriptions, versions, seen), [])

    def test_returns_names_sorted(self):
        subscriptions = {"zeta": ["answer"], "alpha": ["answer"]}
        self.assertEqual(
            eligible_nodes(subscriptions, {"answer": 1}, {}),
            ["alpha", "zeta"],
            "sorted, so a fan out merges its writes the same way every run",
        )


class TestMarkSeen(unittest.TestCase):
    def test_records_the_given_channels(self):
        seen: dict = {}
        mark_seen(seen, "writer", ["answer"], {"answer": 4, "notes": 9})
        self.assertEqual(seen, {"writer": {"answer": 4}})

    def test_records_only_the_channels_passed(self):
        seen: dict = {}
        mark_seen(seen, "writer", ["answer"], {"answer": 4, "notes": 9})
        self.assertNotIn(
            "notes",
            seen["writer"],
            "a node records what it subscribes to, not everything in the state",
        )

    def test_mutates_in_place_and_returns_none(self):
        seen: dict = {"writer": {"answer": 1}}
        result = mark_seen(seen, "writer", ["answer"], {"answer": 2})
        self.assertIsNone(result, "mark_seen updates the map it is given")
        self.assertEqual(seen["writer"]["answer"], 2)

    def test_defaults_a_missing_version_to_zero(self):
        seen: dict = {}
        mark_seen(seen, "writer", ["ghost"], {})
        self.assertEqual(seen, {"writer": {"ghost": 0}})

    def test_a_marked_node_stops_being_eligible(self):
        state = ChannelState(build_channels())
        subscriptions = {"writer": ["answer"]}
        state.apply({"answer": "hello"})
        self.assertEqual(eligible_nodes(subscriptions, state.versions(), {}), ["writer"])

        seen: dict = {}
        mark_seen(seen, "writer", ["answer"], state.versions())
        self.assertEqual(eligible_nodes(subscriptions, state.versions(), seen), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
