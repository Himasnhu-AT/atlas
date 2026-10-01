"""
Checkpoints, resume, and time travel: worked solution.

The engine is the previous two exercises. The checkpointer is a dict of dicts,
and resume, replay and forking are three different reads of it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator


# The engine, from the previous two exercises.


@dataclass
class Channel:
    """A named slot: a reducer, and a callable producing its starting value."""

    name: str
    reducer: Callable[[Any, Any], Any]
    default: Callable[[], Any]


def last_value(current: Any, update: Any) -> Any:
    """Overwrite. The update wins."""
    del current
    return update


def append(current: Any, update: Any) -> list:
    """Accumulate into a new list. A list update contributes its items."""
    if isinstance(update, list):
        return list(current) + update
    return list(current) + [update]


def merge_dicts(current: dict, update: dict) -> dict:
    """Shallow merge into a new dict. Keys in the update win."""
    return {**current, **update}


def add_int(current: int, update: int) -> int:
    """Sum."""
    return current + update


class UnknownChannel(KeyError):
    """A write named a channel the state does not have."""


class SuperStepLimit(RuntimeError):
    """The run used its whole super-step budget with work still to do."""


START = "__start__"
END = "__end__"


def trigger_channel(node: str) -> str:
    """The channel an edge into `node` writes."""
    return f"to:{node}"


class ChannelState:
    """
    The values, the versions, and who has seen what.

    versions_seen and finished are plain attributes rather than private, because
    the checkpointer has to read them and put them back.
    """

    def __init__(self, channels: list[Channel]) -> None:
        self._channels: dict[str, Channel] = {c.name: c for c in channels}
        self._values: dict[str, Any] = {
            name: channel.default() for name, channel in self._channels.items()
        }
        self._versions: dict[str, int] = {name: 0 for name in self._channels}
        self.versions_seen: dict[str, dict[str, int]] = {}
        self.finished: bool = False

    def values(self) -> dict[str, Any]:
        """
        A new dict, holding the SAME value objects.

        Shallow on purpose, because a node reading the state should not pay for a
        deep copy of everything. It does mean a checkpoint that stores this dict
        directly will keep pointing at the live list.
        """
        return dict(self._values)

    def versions(self) -> dict[str, int]:
        return dict(self._versions)

    def apply(self, updates: dict[str, Any]) -> list[str]:
        """Write a batch through the reducers. All or nothing. Returns the names."""
        unknown = sorted(name for name in updates if name not in self._channels)
        if unknown:
            raise UnknownChannel(
                f"no channel named {unknown[0]!r}. "
                f"This state has: {', '.join(sorted(self._channels)) or '(none)'}"
            )
        staged = {
            name: self._channels[name].reducer(self._values[name], update)
            for name, update in updates.items()
        }
        self._values.update(staged)
        for name in staged:
            self._versions[name] += 1
        return sorted(staged)

    def restore(
        self,
        channel_values: dict[str, Any],
        channel_versions: dict[str, int],
        versions_seen: dict[str, dict[str, int]],
    ) -> None:
        """
        Replace the whole state with a checkpoint's contents.

        Copies on the way in, so a restored run mutating its state cannot reach
        back and edit the checkpoint it came from.
        """
        self._values = deepcopy(channel_values)
        self._versions = dict(channel_versions)
        self.versions_seen = deepcopy(versions_seen)


def eligible_nodes(
    subscriptions: dict[str, list[str]],
    versions: dict[str, int],
    versions_seen: dict[str, dict[str, int]],
) -> list[str]:
    """Every node with a subscribed channel newer than the version it saw, sorted."""
    stale = []
    for node, channels in subscriptions.items():
        seen = versions_seen.get(node, {})
        if any(versions.get(name, 0) > seen.get(name, 0) for name in channels):
            stale.append(node)
    return sorted(stale)


def mark_seen(
    versions_seen: dict[str, dict[str, int]],
    node: str,
    channels: list[str],
    versions: dict[str, int],
) -> None:
    """Record the given channels at the given versions, in place."""
    seen = versions_seen.setdefault(node, {})
    for name in channels:
        seen[name] = versions.get(name, 0)


@dataclass
class StepRecord:
    """One super-step: which nodes ran, and which channels their updates touched."""

    index: int
    nodes: list[str]
    updated: list[str]


@dataclass
class RunResult:
    """The final values, the step log, and whether the run reached END."""

    values: dict = field(default_factory=dict)
    steps: list[StepRecord] = field(default_factory=list)
    finished: bool = False


class StateGraph:
    """Nodes, edges, and a scheduler that hands you back control after each step."""

    def __init__(self, channels: list[Channel]) -> None:
        self._channels: dict[str, Channel] = {c.name: c for c in channels}
        self._nodes: dict[str, Callable[[dict], dict | None]] = {}
        self._subscriptions: dict[str, list[str]] = {}
        self._edges: dict[str, list[str]] = {}
        self._routers: dict[str, Callable[[dict], str]] = {}
        self._entry: str | None = None

    def add_node(
        self, name: str, fn: Callable[[dict], dict | None], subscribes: list[str]
    ) -> None:
        if name in self._nodes:
            raise ValueError(f"there is already a node called {name!r}")
        missing = [c for c in subscribes if c not in self._channels]
        if missing:
            raise ValueError(f"node {name!r} subscribes to unknown channel {missing[0]!r}")
        trigger = trigger_channel(name)
        self._channels[trigger] = Channel(trigger, last_value, lambda: 0)
        self._nodes[name] = fn
        self._subscriptions[name] = list(subscribes) + [trigger]

    def add_edge(self, source: str, target: str) -> None:
        if source == START:
            self.set_entry_point(target)
            return
        if source not in self._nodes:
            raise ValueError(f"no node called {source!r}")
        if target != END and target not in self._nodes:
            raise ValueError(f"no node called {target!r}")
        self._edges.setdefault(source, []).append(target)

    def add_conditional_edges(self, source: str, router: Callable[[dict], str]) -> None:
        if source not in self._nodes:
            raise ValueError(f"no node called {source!r}")
        self._routers[source] = router

    def set_entry_point(self, name: str) -> None:
        if name not in self._nodes:
            raise ValueError(f"no node called {name!r}")
        self._entry = name

    def new_state(self) -> ChannelState:
        """A fresh state with the entry point already triggered."""
        if self._entry is None:
            raise ValueError("this graph has no entry point")
        state = ChannelState(list(self._channels.values()))
        state.apply({trigger_channel(self._entry): 1})
        return state

    def run_steps(self, state: ChannelState, max_steps: int = 25) -> Iterator[StepRecord]:
        """
        Run super-steps against `state`, yielding a StepRecord after each.

        The state is mutated in place, so by the time a record is yielded the
        state already holds everything that super-step produced. That is the
        moment to write a checkpoint.

        A node that raises takes the exception straight out of the generator
        before the yield, so the super-step it was in is never checkpointed and
        never half committed.
        """
        index = 0
        tick = 0
        while not state.finished:
            eligible = eligible_nodes(self._subscriptions, state.versions(), state.versions_seen)
            if not eligible:
                return
            if index >= max_steps:
                raise SuperStepLimit(f"{max_steps} super-steps with work still to do")

            snapshot = state.values()
            snapshot_versions = state.versions()
            outputs = [(name, self._nodes[name](dict(snapshot))) for name in eligible]

            updated: list[str] = []
            for name, update in outputs:
                if update:
                    updated.extend(state.apply(update))

            for name in eligible:
                mark_seen(state.versions_seen, name, self._subscriptions[name], snapshot_versions)

            triggers: dict[str, int] = {}
            for name in eligible:
                for target in self._edges.get(name, []):
                    if target == END:
                        state.finished = True
                        continue
                    tick += 1
                    triggers[trigger_channel(target)] = tick
                router = self._routers.get(name)
                if router is not None:
                    target = router(state.values())
                    if target == END:
                        state.finished = True
                    elif target in self._nodes:
                        tick += 1
                        triggers[trigger_channel(target)] = tick
                    else:
                        raise ValueError(f"router on {name!r} returned {target!r}")
            if triggers:
                state.apply(triggers)

            record = StepRecord(index=index, nodes=list(eligible), updated=sorted(set(updated)))
            index += 1
            yield record




# Persistence.


@dataclass
class Checkpoint:
    """The whole state of a run at the end of one super-step."""

    v: int
    id: str
    ts: str
    channel_values: dict
    channel_versions: dict
    versions_seen: dict
    updated_channels: list


def new_checkpoint_id(counter: int) -> str:
    """Zero padded, so string order is chronological order."""
    return f"{counter:010d}"


@dataclass
class CheckpointTuple:
    """A checkpoint, its config, and the config of the one it followed."""

    config: dict
    checkpoint: Checkpoint
    parent_config: dict | None = None


class InMemorySaver:
    """The checkpointer. A dict, and the interface a real one implements."""

    def __init__(self) -> None:
        # thread id -> checkpoint id -> tuple. Nested rather than flat, so one
        # thread's history can never be read through another thread's config.
        self._threads: dict[str, dict[str, CheckpointTuple]] = {}

    def put(
        self, config: dict, checkpoint: Checkpoint, parent_config: dict | None = None
    ) -> dict:
        thread_id = config["thread_id"]
        written = {"thread_id": thread_id, "checkpoint_id": checkpoint.id}
        self._threads.setdefault(thread_id, {})[checkpoint.id] = CheckpointTuple(
            config=dict(written), checkpoint=checkpoint, parent_config=parent_config
        )
        return written

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        stored = self._threads.get(config["thread_id"])
        if not stored:
            return None
        checkpoint_id = config.get("checkpoint_id")
        if checkpoint_id is None:
            # No id means "wherever this thread got to", which is resume.
            # max() on the keys works because the ids are zero padded.
            checkpoint_id = max(stored)
        return stored.get(checkpoint_id)

    def list(self, config: dict, limit: int | None = None) -> list[CheckpointTuple]:
        stored = self._threads.get(config["thread_id"], {})
        newest_first = [stored[key] for key in sorted(stored, reverse=True)]
        if limit is None:
            return newest_first
        return newest_first[:limit]


def run_with_checkpoints(
    graph: StateGraph,
    saver: InMemorySaver,
    config: dict,
    inputs: dict | None = None,
    max_steps: int = 25,
) -> RunResult:
    """Run a graph, writing a checkpoint after every super-step."""
    thread_id = config["thread_id"]
    state = graph.new_state()

    resumed = saver.get_tuple(config)
    parent_config: dict | None = None
    if resumed is not None:
        checkpoint = resumed.checkpoint
        state.restore(
            checkpoint.channel_values, checkpoint.channel_versions, checkpoint.versions_seen
        )
        parent_config = {"thread_id": thread_id, "checkpoint_id": checkpoint.id}

    # After the restore, so a resumed run can be handed new information.
    if inputs:
        state.apply(inputs)

    # Continue the thread's numbering. Starting at 0 on a resume would write ids
    # that already exist and silently rewrite the history.
    counter = len(saver.list({"thread_id": thread_id}))

    steps: list[StepRecord] = []
    for record in graph.run_steps(state, max_steps=max_steps):
        steps.append(record)
        checkpoint = Checkpoint(
            v=1,
            id=new_checkpoint_id(counter),
            ts=datetime.now(timezone.utc).isoformat(),
            # deepcopy, because values() shares its list objects with the live
            # state. Without it every checkpoint in the thread ends up showing
            # the final state, which looks like a bug in the engine.
            channel_values=deepcopy(state.values()),
            channel_versions=state.versions(),
            versions_seen=deepcopy(state.versions_seen),
            updated_channels=list(record.updated),
        )
        parent_config = saver.put({"thread_id": thread_id}, checkpoint, parent_config)
        counter += 1

    return RunResult(values=state.values(), steps=steps, finished=state.finished)


def fork(saver: InMemorySaver, config: dict, checkpoint_id: str, new_thread_id: str) -> dict:
    """Copy one checkpoint into a new thread, so a run can branch."""
    source_thread = config["thread_id"]
    source = saver.get_tuple({"thread_id": source_thread, "checkpoint_id": checkpoint_id})
    if source is None:
        raise KeyError(f"thread {source_thread!r} has no checkpoint {checkpoint_id!r}")

    original = source.checkpoint
    copy = Checkpoint(
        v=original.v,
        id=new_checkpoint_id(0),
        ts=datetime.now(timezone.utc).isoformat(),
        channel_values=deepcopy(original.channel_values),
        channel_versions=dict(original.channel_versions),
        versions_seen=deepcopy(original.versions_seen),
        updated_channels=list(original.updated_channels),
    )
    return saver.put(
        {"thread_id": new_thread_id},
        copy,
        {"thread_id": source_thread, "checkpoint_id": checkpoint_id},
    )
