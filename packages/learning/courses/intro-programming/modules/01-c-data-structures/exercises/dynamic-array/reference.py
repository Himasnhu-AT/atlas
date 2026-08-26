from __future__ import annotations

from typing import Any


class DynamicArray:
    """
    Contiguous resizable dynamic array with geometric growth.
    """

    def __init__(self, initial_capacity: int = 4) -> None:
        """Initialize array with a given initial capacity (minimum 1)."""
        self._capacity = max(1, initial_capacity)
        self._size = 0
        self._buffer: list[Any] = [None] * self._capacity

    def _resize(self, new_capacity: int) -> None:
        new_capacity = max(1, new_capacity)
        new_buffer: list[Any] = [None] * new_capacity
        for i in range(self._size):
            new_buffer[i] = self._buffer[i]
        self._buffer = new_buffer
        self._capacity = new_capacity

    def push_back(self, val: Any) -> None:
        """Append an element to the end of the array, doubling capacity when full."""
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        self._buffer[self._size] = val
        self._size += 1

    def pop_back(self) -> Any:
        """Remove and return the last element. Raises IndexError if array is empty."""
        if self._size == 0:
            raise IndexError("pop_back from empty dynamic array")
        self._size -= 1
        val = self._buffer[self._size]
        self._buffer[self._size] = None
        return val

    def get(self, index: int) -> Any:
        """Return element at index. Raises IndexError if index is out of bounds [0, size - 1]."""
        if index < 0 or index >= self._size:
            raise IndexError(f"Index {index} out of bounds for size {self._size}")
        return self._buffer[index]

    def set(self, index: int, val: Any) -> None:
        """Overwrite element at index. Raises IndexError if index is out of bounds [0, size - 1]."""
        if index < 0 or index >= self._size:
            raise IndexError(f"Index {index} out of bounds for size {self._size}")
        self._buffer[index] = val

    def insert(self, index: int, val: Any) -> None:
        """
        Insert val at index [0, size], shifting subsequent elements right.
        Doubles capacity if the array is full prior to insertion.
        Raises IndexError if index < 0 or index > size.
        """
        if index < 0 or index > self._size:
            raise IndexError(f"Index {index} out of bounds for insertion into size {self._size}")
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        for i in range(self._size, index, -1):
            self._buffer[i] = self._buffer[i - 1]
        self._buffer[index] = val
        self._size += 1

    def remove_at(self, index: int) -> Any:
        """
        Remove and return element at index [0, size - 1], shifting subsequent elements left.
        Raises IndexError if index < 0 or index >= size.
        """
        if index < 0 or index >= self._size:
            raise IndexError(f"Index {index} out of bounds for removal from size {self._size}")
        val = self._buffer[index]
        for i in range(index, self._size - 1):
            self._buffer[i] = self._buffer[i + 1]
        self._size -= 1
        self._buffer[self._size] = None
        return val

    def size(self) -> int:
        """Return the number of active elements in the array."""
        return self._size

    def capacity(self) -> int:
        """Return the total allocated element slots."""
        return self._capacity

    def shrink_to_fit(self) -> None:
        """Reduce capacity to match max(size, 1), releasing excess memory."""
        target_capacity = max(self._size, 1)
        if target_capacity != self._capacity:
            self._resize(target_capacity)
