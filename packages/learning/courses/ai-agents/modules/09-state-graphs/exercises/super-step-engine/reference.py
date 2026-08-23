"""
The super step: worked solution.

The state layer is the previous exercise. The engine underneath it is the part
that makes a graph a graph: eligibility from versions, one snapshot per step,
and a merge that happens only after every node in the step has returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# The state layer, from the previous exercise.


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


# The engine.


START = "__start__"
END = "__end__"


def trigger_channel(node: str) -> str:
    """The channel an edge into `node` writes."""
    return f"to:{node}"


class SuperStepLimit(RuntimeError):
    """The run used its whole super-step budget. Carries `.steps`."""


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
    """Nodes, edges, and the scheduler that runs them."""

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
        if name in (START, END):
            raise ValueError(f"{name!r} is reserved for the virtual start and end nodes")

        missing = [c for c in subscribes if c not in self._channels]
        if missing:
            raise ValueError(
                f"node {name!r} subscribes to {missing[0]!r}, which is not a channel. "
                f"Declared channels: {', '.join(sorted(self._channels))}"
            )

        # The trigger channel is what an edge writes. Creating it with the node
        # rather than with the edge means add_node and add_edge can be called in
        # either order, and a conditional router can name any node as its target.
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
        if source in self._routers:
            raise ValueError(
                f"node {source!r} already has conditional edges. A node routes "
                f"statically or dynamically, not both."
            )
        self._edges.setdefault(source, []).append(target)

    def add_conditional_edges(self, source: str, router: Callable[[dict], str]) -> None:
        if source not in self._nodes:
            raise ValueError(f"no node called {source!r}")
        if source in self._edges:
            raise ValueError(
                f"node {source!r} already has static edges. A node routes "
                f"statically or dynamically, not both."
            )
        self._routers[source] = router

    def set_entry_point(self, name: str) -> None:
        if name not in self._nodes:
            raise ValueError(f"no node called {name!r}")
        self._entry = name

    def run(self, inputs: dict, max_steps: int = 25) -> RunResult:
        if self._entry is None:
            raise ValueError(
                "this graph has no entry point: call set_entry_point(name), or "
                "add_edge(START, name)"
            )

        state = ChannelState(list(self._channels.values()))
        if inputs:
            state.apply(inputs)
        # Triggering the entry point is an ordinary write. Nothing about the
        # first super-step is special, which is what keeps resume simple later.
        state.apply({trigger_channel(self._entry): 1})

        versions_seen: dict[str, dict[str, int]] = {}
        steps: list[StepRecord] = []
        finished = False
        tick = 0

        while not finished:
            eligible = eligible_nodes(self._subscriptions, state.versions(), versions_seen)
            if not eligible:
                break
            if len(steps) >= max_steps:
                limit = SuperStepLimit(
                    f"{max_steps} super-steps went by with {', '.join(eligible)} still "
                    f"eligible. Something in this graph keeps waking something else."
                )
                limit.steps = steps
                raise limit

            snapshot = state.values()
            snapshot_versions = state.versions()

            # Every node in the step reads the same values. Collect the outputs
            # first and merge afterwards, so the result does not depend on the
            # order the nodes happened to be called in.
            outputs = [(name, self._nodes[name](dict(snapshot))) for name in eligible]

            updated: list[str] = []
            for name, update in outputs:
                if update:
                    updated.extend(state.apply(update))

            # The versions from the start of the step, deliberately. A node that
            # writes a channel it subscribes to should wake itself again.
            for name in eligible:
                mark_seen(versions_seen, name, self._subscriptions[name], snapshot_versions)

            triggers: dict[str, int] = {}
            for name in eligible:
                for target in self._edges.get(name, []):
                    if target == END:
                        finished = True
                        continue
                    tick += 1
                    triggers[trigger_channel(target)] = tick
                router = self._routers.get(name)
                if router is not None:
                    # After the merge, so the router can read what the node just
                    # wrote. Routing on the pre-step snapshot is the classic bug.
                    target = router(state.values())
                    if target == END:
                        finished = True
                    elif target in self._nodes:
                        tick += 1
                        triggers[trigger_channel(target)] = tick
                    else:
                        raise ValueError(
                            f"the router on {name!r} returned {target!r}, which is "
                            f"neither a node nor END"
                        )
            if triggers:
                state.apply(triggers)

            steps.append(
                StepRecord(index=len(steps), nodes=list(eligible), updated=sorted(set(updated)))
            )

        return RunResult(values=state.values(), steps=steps, finished=finished)
