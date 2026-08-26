from __future__ import annotations

from typing import Any


class DynamicArray:
    """
    Contiguous resizable dynamic array with geometric growth.
    """

    def __init__(self, initial_capacity: int = 4) -> None:
        """Initialize array with a given initial capacity (minimum 1)."""
        raise NotImplementedError

    def push_back(self, val: Any) -> None:
        """Append an element to the end of the array, doubling capacity when full."""
        raise NotImplementedError

    def pop_back(self) -> Any:
        """Remove and return the last element. Raises IndexError if array is empty."""
        raise NotImplementedError

    def get(self, index: int) -> Any:
        """Return element at index. Raises IndexError if index is out of bounds [0, size - 1]."""
        raise NotImplementedError

    def set(self, index: int, val: Any) -> None:
        """Overwrite element at index. Raises IndexError if index is out of bounds [0, size - 1]."""
        raise NotImplementedError

    def insert(self, index: int, val: Any) -> None:
        """
        Insert val at index [0, size], shifting subsequent elements right.
        Doubles capacity if the array is full prior to insertion.
        Raises IndexError if index < 0 or index > size.
        """
        raise NotImplementedError

    def remove_at(self, index: int) -> Any:
        """
        Remove and return element at index [0, size - 1], shifting subsequent elements left.
        Raises IndexError if index < 0 or index >= size.
        """
        raise NotImplementedError

    def size(self) -> int:
        """Return the number of active elements in the array."""
        raise NotImplementedError

    def capacity(self) -> int:
        """Return the total allocated element slots."""
        raise NotImplementedError

    def shrink_to_fit(self) -> None:
        """Reduce capacity to match max(size, 1), releasing excess memory."""
        raise NotImplementedError
