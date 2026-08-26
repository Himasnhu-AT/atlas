from __future__ import annotations

from typing import Any, List, Optional, Tuple


class GCNode:
    """
    A heap-allocated object tracked by the garbage collector.
    """

    def __init__(self, node_id: str, payload: Any = None) -> None:
        """Initialize a GC heap node with an identifier, payload, and reference list."""
        self.node_id: str = node_id
        self.payload: Any = payload
        self.references: list[GCNode] = []
        self.is_marked: bool = False

    def add_reference(self, target: GCNode) -> None:
        """Add a directed reference from this node to another heap node."""
        raise NotImplementedError

    def remove_reference(self, target: GCNode) -> None:
        """Remove an existing reference to the target heap node."""
        raise NotImplementedError


class MarkAndSweepGC:
    """
    Tracing mark-and-sweep garbage collector supporting cycle detection.
    """

    def __init__(self) -> None:
        """Initialize the allocator tracking registry and root set."""
        self.allocated_nodes: dict[str, GCNode] = {}
        self.roots: set[GCNode] = set()

    def allocate(self, node_id: str, payload: Any = None) -> GCNode:
        """Allocate and track a new heap node in the garbage collector."""
        raise NotImplementedError

    def add_root(self, node: GCNode) -> None:
        """Register a heap node as an active root (e.g. stack variable or global)."""
        raise NotImplementedError

    def remove_root(self, node: GCNode) -> None:
        """Unregister a heap node from the active root set."""
        raise NotImplementedError

    def collect(self) -> tuple[int, list[str]]:
        """
        Execute mark-and-sweep garbage collection.

        Traces reachability from active roots, sweeps unreachable nodes from allocator
        tracking, and returns a tuple of (freed_count, freed_node_ids).
        """
        raise NotImplementedError

    def get_live_count(self) -> int:
        """Return the count of active objects currently tracked in heap storage."""
        raise NotImplementedError
