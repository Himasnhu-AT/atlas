"""
Channels and reducers.

The typed state layer a graph runtime sits on. A channel is a named slot with a
reducer and a version number. Writing to it runs the reducer and bumps the
version, and the versions are what tell the scheduler which nodes are stale.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Channel:
    """
    One named slot in the graph's state.

    Attributes:
        name: the key nodes read and write.
        reducer: called as reducer(current, update) and returns the new value.
            Reducers must be pure: build a new value, never mutate `current`.
        default: a zero-argument callable producing the starting value. It is a
            callable rather than a value so every ChannelState gets its own,
            which is the same reason dataclasses make you write
            field(default_factory=list).
    """

    name: str
    reducer: Callable[[Any, Any], Any]
    default: Callable[[], Any]


def last_value(current: Any, update: Any) -> Any:
    """
    Overwrite. The update wins and the previous value is discarded.

    The default reducer, and the right one for anything where only the newest
    answer matters.
    """
    raise NotImplementedError


def append(current: Any, update: Any) -> list:
    """
    Accumulate into a list.

    Return a NEW list: list(current) plus the update. When the update is itself
    a list, extend by its items rather than nesting it, so a node can contribute
    several entries in one write.

    Returning `current` after calling current.append(update) would pass a casual
    test and then quietly share one list between every state that was built from
    the same Channel object.
    """
    raise NotImplementedError


def merge_dicts(current: dict, update: dict) -> dict:
    """
    Shallow merge. Keys in the update win, keys only in `current` survive.

    Return a new dict.
    """
    raise NotImplementedError


def add_int(current: int, update: int) -> int:
    """Sum. Useful for counters, token totals, and retry budgets."""
    raise NotImplementedError


class UnknownChannel(KeyError):
    """
    A write named a channel the state does not have.

    It subclasses KeyError because that is what a caller reaching for a missing
    key would already be catching. Typos in channel names are the most common
    bug in graph code, and failing loudly at the write is what makes them cheap.
    """


class ChannelState:
    """
    The values and the versions, together.

    A version starts at 0 and goes up by exactly one every time apply() touches
    that channel, whether or not the value actually changed. Version equality is
    how the scheduler decides that a node has already seen everything it
    subscribes to, so an update that happens to be identical still has to count.
    """

    def __init__(self, channels: list[Channel]) -> None:
        """
        Build the state from a list of channels.

        Call each channel's default() here, once per state. Store the value and
        a version of 0 for every channel.
        """
        raise NotImplementedError

    def values(self) -> dict[str, Any]:
        """
        The current value of every channel.

        Return a new dict, so a caller poking at the result cannot rewrite the
        state behind your back.
        """
        raise NotImplementedError

    def versions(self) -> dict[str, int]:
        """The current version of every channel, as a new dict."""
        raise NotImplementedError

    def apply(self, updates: dict[str, Any]) -> list[str]:
        """
        Write a batch of updates through their reducers.

        Each key routes to its channel's reducer, and the channel's version goes
        up by exactly one. Channels not named in `updates` are untouched: same
        value, same version.

        This is all or nothing. Check every key before you write anything, and
        stage the reduced values so a reducer that raises halfway through cannot
        leave the state half updated. A partially applied super-step is the
        worst thing that can happen to a graph runtime, because the checkpoint
        that gets written afterwards looks perfectly valid.

        Returns:
            The names touched, sorted alphabetically.

        Raises:
            UnknownChannel: a key has no channel. Nothing is applied.
        """
        raise NotImplementedError


def eligible_nodes(
    subscriptions: dict[str, list[str]],
    versions: dict[str, int],
    versions_seen: dict[str, dict[str, int]],
) -> list[str]:
    """
    Which nodes have unseen work.

    Args:
        subscriptions: node name to the channels that wake it.
        versions: the state's current channel versions.
        versions_seen: node name to the versions that node last read. A node
            with no entry has seen nothing, and a channel with no entry was last
            seen at version 0.

    A node is eligible when any channel it subscribes to has a current version
    strictly greater than the version that node has seen. Strictly greater
    matters: use >= and every node runs forever.

    Returns:
        The eligible node names, sorted alphabetically. Sorted rather than in
        insertion order because the order decides how writes merge inside a
        super-step, and a run you cannot reproduce is not worth debugging.
    """
    raise NotImplementedError


def mark_seen(
    versions_seen: dict[str, dict[str, int]],
    node: str,
    channels: list[str],
    versions: dict[str, int],
) -> None:
    """
    Record that `node` has now seen `channels` at their current versions.

    Mutates `versions_seen` in place and returns None. Record only the channels
    passed, and take the version from `versions`, defaulting to 0 for a channel
    that is not there.

    The caller decides which versions to hand in. The scheduler passes the
    versions as of the start of the super-step, not the versions after the
    step's writes landed, which is what lets a node that writes a channel it
    subscribes to wake itself up again on the next step.
    """
    raise NotImplementedError
