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
        node = Node(val, prev=None, next=self.head)
        if self.head is None:
            self.head = node
            self.tail = node
        else:
            self.head.prev = node
            self.head = node
        self._size += 1
        return node

    def push_back(self, val: Any) -> Node:
        """Insert a new node with value val at the back of the list. Return the new node."""
        node = Node(val, prev=self.tail, next=None)
        if self.tail is None:
            self.head = node
            self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self._size += 1
        return node

    def pop_front(self) -> Any:
        """Remove and return the value from the front node. Raise IndexError if empty."""
        if self.head is None:
            raise IndexError("pop_front from empty list")
        removed = self.head
        self.head = removed.next
        if self.head is not None:
            self.head.prev = None
        else:
            self.tail = None
        removed.prev = None
        removed.next = None
        self._size -= 1
        return removed.val

    def pop_back(self) -> Any:
        """Remove and return the value from the back node. Raise IndexError if empty."""
        if self.tail is None:
            raise IndexError("pop_back from empty list")
        removed = self.tail
        self.tail = removed.prev
        if self.tail is not None:
            self.tail.next = None
        else:
            self.head = None
        removed.prev = None
        removed.next = None
        self._size -= 1
        return removed.val

    def remove_node(self, node: Node) -> None:
        """Unlink an existing node from the list in O(1) time."""
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = None
        self._size -= 1

    def move_to_front(self, node: Node) -> None:
        """Splice an existing node to the front of the list in O(1) time."""
        if self.head is node or self._size <= 1:
            return

        # Unlink node from its current position
        if node.prev is not None:
            node.prev.next = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        # Insert node at head
        node.prev = None
        node.next = self.head
        if self.head is not None:
            self.head.prev = node
        self.head = node

    def to_list(self) -> list[Any]:
        """Convert the list contents to a Python list from head to tail."""
        result: list[Any] = []
        curr = self.head
        while curr is not None:
            result.append(curr.val)
            curr = curr.next
        return result

    def size(self) -> int:
        """Return the count of active nodes in the list."""
        return self._size
