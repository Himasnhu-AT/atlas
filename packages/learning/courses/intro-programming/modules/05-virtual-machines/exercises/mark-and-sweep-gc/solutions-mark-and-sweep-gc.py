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
        if target not in self.references:
            self.references.append(target)

    def remove_reference(self, target: GCNode) -> None:
        """Remove an existing reference to the target heap node."""
        if target in self.references:
            self.references.remove(target)


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
        node = GCNode(node_id, payload)
        self.allocated_nodes[node_id] = node
        return node

    def add_root(self, node: GCNode) -> None:
        """Register a heap node as an active root (e.g. stack variable or global)."""
        self.roots.add(node)

    def remove_root(self, node: GCNode) -> None:
        """Unregister a heap node from the active root set."""
        self.roots.discard(node)

    def collect(self) -> tuple[int, list[str]]:
        """
        Execute mark-and-sweep garbage collection.

        Traces reachability from active roots, sweeps unreachable nodes from allocator
        tracking, and returns a tuple of (freed_count, freed_node_ids).
        """
        # Reset mark bits on all allocated nodes
        for node in self.allocated_nodes.values():
            node.is_marked = False

        # Mark phase: Traverse reachable object graph from active roots
        worklist: list[GCNode] = []
        for root in self.roots:
            if root.node_id in self.allocated_nodes:
                root.is_marked = True
                worklist.append(root)

        while worklist:
            curr = worklist.pop()
            for ref in curr.references:
                if not ref.is_marked and ref.node_id in self.allocated_nodes:
                    ref.is_marked = True
                    worklist.append(ref)

        # Sweep phase: Reclaim unmarked nodes and reset mark bits on survivors
        freed_node_ids: list[str] = []
        surviving_nodes: dict[str, GCNode] = {}

        for node_id, node in self.allocated_nodes.items():
            if not node.is_marked:
                freed_node_ids.append(node_id)
            else:
                node.is_marked = False
                surviving_nodes[node_id] = node

        self.allocated_nodes = surviving_nodes
        return (len(freed_node_ids), freed_node_ids)

    def get_live_count(self) -> int:
        """Return the count of active objects currently tracked in heap storage."""
        return len(self.allocated_nodes)
