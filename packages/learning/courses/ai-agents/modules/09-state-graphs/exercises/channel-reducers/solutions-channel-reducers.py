"""
Channels and reducers: worked solution.

The typed state layer a graph runtime sits on. A channel is a named slot with a
reducer and a version number, and the versions are what tell the scheduler which
nodes are stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Channel:
    """
    One named slot in the graph's state.

    `default` is a callable rather than a value so every ChannelState gets its
    own, which is the same reason dataclasses make you write
    field(default_factory=list).
    """

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
        # default() is called here, once per state. Calling it once per Channel
        # instead would hand the same list to every state built from it.
        self._values: dict[str, Any] = {
            name: channel.default() for name, channel in self._channels.items()
        }
        self._versions: dict[str, int] = {name: 0 for name in self._channels}

    def values(self) -> dict[str, Any]:
        return dict(self._values)

    def versions(self) -> dict[str, int]:
        return dict(self._versions)

    def apply(self, updates: dict[str, Any]) -> list[str]:
        unknown = sorted(name for name in updates if name not in self._channels)
        if unknown:
            raise UnknownChannel(
                f"no channel named {unknown[0]!r}. "
                f"This state has: {', '.join(sorted(self._channels)) or '(none)'}"
            )

        # Stage first, commit second. A reducer that raises on the third key
        # must not leave the first two written, because the checkpoint taken
        # after a half applied step looks entirely valid from the outside.
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
    """Every node with a subscribed channel newer than the version it saw."""
    stale = []
    for node, channels in subscriptions.items():
        seen = versions_seen.get(node, {})
        # Strictly greater. With >= a node that has seen version 0 of a channel
        # sitting at version 0 would be eligible forever.
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
