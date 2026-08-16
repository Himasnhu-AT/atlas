"""
Checkpoints, resume, and time travel.

Everything above the line is the engine from the previous two exercises,
condensed and finished. The one change: run_steps is a generator that yields a
StepRecord after each super-step, which is the hook a checkpointer needs.

Your job is persistence. Write the state after every super-step and three
features you did not build fall out of it: resume after a crash, replay from an
earlier point, and fork a run into an alternative branch.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterator


# The engine, from the previous two exercises. Nothing below needs changing.


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


# Persistence. This part is yours.


@dataclass
class Checkpoint:
    """
    The whole state of a run at the end of one super-step.

    These are the real fields, in the real order. There is nothing else in a
    LangGraph checkpoint, which is the point of the lesson: resume, replay and
    forking are all reads of this one record.

    Attributes:
        v: the format version. Always 1 here. Present because the day you change
            the shape of this record, there are already checkpoints on disk in
            the old shape.
        id: sorts chronologically as a string. See new_checkpoint_id.
        ts: an ISO 8601 timestamp, for humans. Never sort on it: two super-steps
            can land in the same microsecond, and then your history is guesswork.
        channel_values: every channel value, deep copied at write time.
        channel_versions: every channel version.
        versions_seen: node name to the versions that node had read.
        updated_channels: what this super-step's nodes wrote.
    """

    v: int
    id: str
    ts: str
    channel_values: dict
    channel_versions: dict
    versions_seen: dict
    updated_channels: list


def new_checkpoint_id(counter: int) -> str:
    """
    A checkpoint id that sorts chronologically as a string.

    Zero pad the counter to ten digits, so "0000000002" sorts before
    "0000000010". Plain str(counter) gives you "10" before "2", and the bug
    shows up as history that is subtly out of order rather than as a crash.

    Real implementations use a UUIDv6 or a ULID, which is the same trick with a
    timestamp in the high bits.
    """
    raise NotImplementedError


@dataclass
class CheckpointTuple:
    """
    A checkpoint plus where it sits.

    Attributes:
        config: identifies this checkpoint: thread_id and checkpoint_id.
        checkpoint: the record itself.
        parent_config: the checkpoint this one followed, or None for the first
            in a thread. This is the only thing making the history a tree rather
            than a list, and it is what lets a fork point back at its origin.
    """

    config: dict
    checkpoint: Checkpoint
    parent_config: dict | None = None


class InMemorySaver:
    """
    The checkpointer. A dict, and the interface a real one implements.

    A config is a dict with a `thread_id` and an optional `checkpoint_id`. A
    thread is one conversation, one run, one user session: whatever you want
    resumable. Swapping this for Postgres or SQLite changes these three methods
    and nothing else in the system.
    """

    def __init__(self) -> None:
        """
        Set up the storage.

        Keying by thread and then by checkpoint id is enough. Two threads must
        never be able to see each other's checkpoints, so do not flatten them
        into one dict of ids.
        """
        raise NotImplementedError

    def put(
        self, config: dict, checkpoint: Checkpoint, parent_config: dict | None = None
    ) -> dict:
        """
        Store one checkpoint under config["thread_id"].

        Returns:
            The config for what was just written: thread_id, plus checkpoint_id
            filled in from the checkpoint's own id. Callers chain on this, using
            it as the parent_config of the next put.
        """
        raise NotImplementedError

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        """
        Fetch one checkpoint.

        With a checkpoint_id in the config, that exact one. Without, the newest
        in the thread. That default is the whole of resume: a caller that passes
        only a thread_id picks up where the thread left off.

        Returns:
            The CheckpointTuple, or None when the thread or the id is unknown.
            None rather than an exception, because "this thread has never run"
            is the ordinary first call, not a failure.
        """
        raise NotImplementedError

    def list(self, config: dict, limit: int | None = None) -> list[CheckpointTuple]:
        """
        Every checkpoint in the thread, newest first, at most `limit` of them.

        Named `list` because that is what the real interface calls it. Inside
        the class body that name now refers to this method, which is one more
        reason `from __future__ import annotations` is at the top of the file:
        the annotations here are strings and never get evaluated.

        Returns:
            An empty list for an unknown thread.
        """
        raise NotImplementedError


def run_with_checkpoints(
    graph: StateGraph,
    saver: InMemorySaver,
    config: dict,
    inputs: dict | None = None,
    max_steps: int = 25,
) -> RunResult:
    """
    Run a graph, writing a checkpoint after every super-step.

    The order of operations:
      - build a fresh state with graph.new_state()
      - ask the saver for the checkpoint the config names. When there is one,
        restore its channel_values, channel_versions and versions_seen, and
        remember its config as the first parent
      - apply `inputs` when given, after the restore, so a resumed run can be
        handed new information
      - drive graph.run_steps(state, max_steps=max_steps) and write one
        checkpoint per record yielded, each one's parent_config naming the one
        before it

    Two things that look like details and are not. Deep copy the values into the
    checkpoint: state.values() hands back a new dict holding the same list
    objects, so a checkpoint that stores it directly will keep growing as the run
    continues, and every checkpoint in the thread ends up showing the final
    state. And take the counter for new_checkpoint_id from how many checkpoints
    the thread already has, or a resumed run starts numbering at zero and
    overwrites its own history.

    Args:
        graph: the graph to run.
        saver: where checkpoints go.
        config: thread_id, and optionally checkpoint_id to start from a
            particular point rather than the newest.
        inputs: starting writes, or None.
        max_steps: super-steps allowed in THIS run, not in the thread's life.

    Returns:
        RunResult for this run. `steps` covers only the super-steps this call
        ran, which after a resume is the tail of the work rather than all of it.
    """
    raise NotImplementedError


def fork(saver: InMemorySaver, config: dict, checkpoint_id: str, new_thread_id: str) -> dict:
    """
    Copy one checkpoint into a new thread, so a run can branch.

    The copy becomes the first checkpoint of `new_thread_id`, gets a fresh id
    from new_checkpoint_id(0), and carries a parent_config naming the thread and
    checkpoint it came from. Deep copy the values: a fork sharing lists with its
    origin is a fork that edits the past.

    The original thread is not touched. That is the whole feature: run the fork,
    compare it against the original, keep the better one.

    Args:
        saver: the checkpointer holding both threads.
        config: names the source thread.
        checkpoint_id: the checkpoint in that thread to branch from.
        new_thread_id: the thread to create.

    Returns:
        The config for the new thread's first checkpoint, ready to hand to
        run_with_checkpoints.

    Raises:
        KeyError: no such checkpoint in that thread.
    """
    raise NotImplementedError
