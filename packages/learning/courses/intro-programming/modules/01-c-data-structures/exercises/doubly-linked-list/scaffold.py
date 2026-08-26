from __future__ import annotations

from typing import Any, Optional


class Node:
    """A node in a doubly linked list."""

    def __init__(
        self,
        val: Any,
        prev: Optional[Node] = None,
        next: Optional[Node] = None,
    ) -> None:
        self.val = val
        self.prev = prev
        self.next = next


class DoublyLinkedList:
    """
    Doubly linked list container managing direct head and tail references
    without dummy sentinel nodes.
    """

    def __init__(self) -> None:
        """Initialize an empty doubly linked list."""
        self.head: Optional[Node] = None
        self.tail: Optional[Node] = None
        self._size: int = 0

    def push_front(self, val: Any) -> Node:
        """Insert a new node with value val at the front of the list. Return the new node."""
        raise NotImplementedError

    def push_back(self, val: Any) -> Node:
        """Insert a new node with value val at the back of the list. Return the new node."""
        raise NotImplementedError

    def pop_front(self) -> Any:
        """Remove and return the value from the front node. Raise IndexError if empty."""
        raise NotImplementedError

    def pop_back(self) -> Any:
        """Remove and return the value from the back node. Raise IndexError if empty."""
        raise NotImplementedError

    def remove_node(self, node: Node) -> None:
        """Unlink an existing node from the list in O(1) time."""
        raise NotImplementedError

    def move_to_front(self, node: Node) -> None:
        """Splice an existing node to the front of the list in O(1) time."""
        raise NotImplementedError

    def to_list(self) -> list[Any]:
        """Convert the list contents to a Python list from head to tail."""
        raise NotImplementedError

    def size(self) -> int:
        """Return the count of active nodes in the list."""
        raise NotImplementedError
