from __future__ import annotations

from typing import Any


class MinHeapPriorityQueue:
    """
    Min-heap based priority queue backed by a complete binary tree in a flat array.
    """

    def __init__(self) -> None:
        """
        Initialize an empty priority queue.
        """
        raise NotImplementedError

    def push(self, priority: float, value: Any) -> None:
        """
        Insert an item with a priority and sift it up to maintain the min-heap property.
        """
        raise NotImplementedError

    def pop(self) -> tuple[float, Any]:
        """
        Remove and return the item with the minimum priority (priority, value).
        Raises IndexError if the queue is empty.
        """
        raise NotImplementedError

    def peek(self) -> tuple[float, Any]:
        """
        Return the item with the minimum priority without removing it.
        Raises IndexError if the queue is empty.
        """
        raise NotImplementedError

    def size(self) -> int:
        """
        Return the number of items stored in the priority queue.
        """
        raise NotImplementedError

    def is_empty(self) -> bool:
        """
        Return True if the priority queue contains no items, False otherwise.
        """
        raise NotImplementedError

    def heapify(self, items: list[tuple[float, Any]]) -> None:
        """
        Build the min-heap in-place from a list of (priority, value) tuples in O(n) time.
        """
        raise NotImplementedError
