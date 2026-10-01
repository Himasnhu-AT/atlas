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
        self._heap: list[tuple[float, Any]] = []

    def _sift_up(self, idx: int) -> None:
        while idx > 0:
            parent = (idx - 1) // 2
            if self._heap[idx][0] < self._heap[parent][0]:
                self._heap[idx], self._heap[parent] = self._heap[parent], self._heap[idx]
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        n = len(self._heap)
        while True:
            smallest = idx
            left = 2 * idx + 1
            right = 2 * idx + 2

            if left < n and self._heap[left][0] < self._heap[smallest][0]:
                smallest = left
            if right < n and self._heap[right][0] < self._heap[smallest][0]:
                smallest = right

            if smallest != idx:
                self._heap[idx], self._heap[smallest] = self._heap[smallest], self._heap[idx]
                idx = smallest
            else:
                break

    def push(self, priority: float, value: Any) -> None:
        """
        Insert an item with a priority and sift it up to maintain the min-heap property.
        """
        self._heap.append((priority, value))
        self._sift_up(len(self._heap) - 1)

    def pop(self) -> tuple[float, Any]:
        """
        Remove and return the item with the minimum priority (priority, value).
        Raises IndexError if the queue is empty.
        """
        if not self._heap:
            raise IndexError("pop from empty priority queue")
        if len(self._heap) == 1:
            return self._heap.pop()

        root = self._heap[0]
        self._heap[0] = self._heap.pop()
        self._sift_down(0)
        return root

    def peek(self) -> tuple[float, Any]:
        """
        Return the item with the minimum priority without removing it.
        Raises IndexError if the queue is empty.
        """
        if not self._heap:
            raise IndexError("peek from empty priority queue")
        return self._heap[0]

    def size(self) -> int:
        """
        Return the number of items stored in the priority queue.
        """
        return len(self._heap)

    def is_empty(self) -> bool:
        """
        Return True if the priority queue contains no items, False otherwise.
        """
        return len(self._heap) == 0

    def heapify(self, items: list[tuple[float, Any]]) -> None:
        """
        Build the min-heap in-place from a list of (priority, value) tuples in O(n) time.
        """
        self._heap = list(items)
        n = len(self._heap)
        for i in range((n - 2) // 2, -1, -1):
            self._sift_down(i)
