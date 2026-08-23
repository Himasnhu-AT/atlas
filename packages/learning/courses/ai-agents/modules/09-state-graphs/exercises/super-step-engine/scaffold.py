"""
The super step.

Everything above the line is the state layer you built in the previous exercise,
finished and out of your way. Your job is the scheduler: work out which nodes are
eligible, run them all against one snapshot, merge their writes afterwards, and
follow the edges.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# The state layer, from the previous exercise. Nothing below needs changing.


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


class ChannelState:
    """The values and the versions, together."""

    def __init__(self, channels: list[Channel]) -> None:
        self._channels: dict[str, Channel] = {c.name: c for c in channels}
        self._values: dict[str, Any] = {
            name: channel.default() for name, channel in self._channels.items()
        }
        self._versions: dict[str, int] = {name: 0 for name in self._channels}

    def values(self) -> dict[str, Any]:
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


# The engine. This part is yours.


#: Virtual nodes. `add_edge(START, "a")` is how you name the entry point, and an
#: edge to END ends the run. They are plain strings because a checkpoint has to
#: survive being written to disk, and a string does that with no help.
START = "__start__"
END = "__end__"


def trigger_channel(node: str) -> str:
    """
    The name of the channel that wakes `node`.

    An edge is not a special kind of object in a graph runtime. It is a channel
    plus a subscription: when a runs, the engine writes to the channel b listens
    on, and b becomes eligible. Naming that channel is all `add_edge` does.
    """
    return f"to:{node}"


class SuperStepLimit(RuntimeError):
    """
    The run used its whole super-step budget without finishing.

    The engine attaches the StepRecords it collected before giving up as
    `.steps`, because the shape of a runaway graph is exactly what you need to
    see and exactly what a bare exception throws away.
    """


@dataclass
class StepRecord:
    """
    One super-step, after the fact.

    Attributes:
        index: 0 for the first super-step.
        nodes: the nodes that ran in it, sorted.
        updated: the channels their updates touched, sorted and deduplicated.
            Trigger channels are engine bookkeeping and are not listed here.
    """

    index: int
    nodes: list[str]
    updated: list[str]


@dataclass
class RunResult:
    """
    Everything a run produced.

    Attributes:
        values: the final channel values.
        steps: one StepRecord per super-step, in order.
        finished: True when the run reached END. False when it simply ran out of
            eligible nodes, which is a different thing and worth being able to
            tell apart.
    """

    values: dict = field(default_factory=dict)
    steps: list[StepRecord] = field(default_factory=list)
    finished: bool = False


class StateGraph:
    """
    Nodes, edges, and the scheduler that runs them.

    A node is a plain function taking the current values and returning a partial
    update, or None when it has nothing to say. It never mutates what it is
    given and it never sees the state object itself.
    """

    def __init__(self, channels: list[Channel]) -> None:
        """
        Declare the graph's channels.

        Keep the channels somewhere you can add to: add_node creates one trigger
        channel per node on top of these.
        """
        raise NotImplementedError

    def add_node(self, name: str, fn: Callable[[dict], dict | None], subscribes: list[str]) -> None:
        """
        Add a node.

        Args:
            name: unique within the graph.
            fn: called as fn(values) and returns a partial update dict, or None.
            subscribes: the channels whose movement wakes this node. Reading a
                channel and subscribing to it are different things: a node sees
                every value in the state when it runs, and subscribes only to
                the ones that should cause it to run again.

        Also create the node's trigger channel, trigger_channel(name), as a
        last_value channel starting at 0, and subscribe the node to it. That is
        what makes an incoming edge able to wake this node.

        Raises:
            ValueError: the name is already taken, the name is START or END, or
                a subscribed channel was never declared. That last one is worth
                catching here. A typo in a subscription does not crash, it
                produces a node that silently never runs, and you will spend an
                hour on it.
        """
        raise NotImplementedError

    def add_edge(self, source: str, target: str) -> None:
        """
        Run `target` after `source`.

        After source runs, the engine writes a counter into the target's trigger
        channel, which is a real write through last_value and so bumps a real
        version, which is what makes the target eligible on the next super-step.

        Two virtual endpoints: a source of START names the graph's entry point
        (the same thing set_entry_point does), and a target of END means the run
        is finished once source has run.

        Raises:
            ValueError: either endpoint is a node that does not exist, or the
                source already has conditional edges.
        """
        raise NotImplementedError

    def add_conditional_edges(self, source: str, router: Callable[[dict], str]) -> None:
        """
        Decide where to go after `source` at run time.

        The router is called with the values as they stand AFTER the super-step's
        writes have been merged, so it can read what source just produced. It
        returns a node name, or END to finish the run.

        Raises:
            ValueError: source is not a node, or it already has static edges. A
                node routes one way or the other, not both.
        """
        raise NotImplementedError

    def set_entry_point(self, name: str) -> None:
        """
        Name the node that runs first.

        Raises:
            ValueError: no such node.
        """
        raise NotImplementedError

    def run(self, inputs: dict, max_steps: int = 25) -> RunResult:
        """
        Run the graph to quiescence, to END, or into the wall.

        One super-step:
          - work out the eligible nodes from the subscriptions and versions_seen
          - stop if there are none, or if a previous step reached END
          - take ONE snapshot of the values and give every eligible node its own
            copy of it, so two nodes in the same step cannot see each other's
            work and the run does not depend on which one you called first
          - only once every node has returned, merge the updates through the
            reducers, in sorted node order
          - mark each node as having seen its subscriptions at the versions from
            the START of the step, not the versions after the merge. Marking the
            later versions would stop a node ever waking itself, which is how a
            loop in the graph is built
          - follow the edges: write a counter into each target's trigger channel,
            or set finished for END. Conditional routers run here, after the
            merge
          - append a StepRecord

        Before the first step, seed the channels named in `inputs` through their
        reducers, then trigger the entry point.

        Args:
            inputs: starting writes, keyed by channel. Pass an empty dict for none.
            max_steps: super-steps allowed. Not model calls, not nodes: a fan out
                of five nodes is one super-step.

        Returns:
            RunResult with the final values, one StepRecord per super-step, and
            whether the run reached END.

        Raises:
            ValueError: the graph has no entry point, or a router returned a name
                that is neither a node nor END.
            SuperStepLimit: max_steps super-steps went by with work still to do.
                Attach the records collected so far as `.steps` on the exception.
        """
        raise NotImplementedError
