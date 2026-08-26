from __future__ import annotations

from typing import Any


class OpenAddressingHashMap:
    """
    High-performance hash map implementing open addressing with linear probing
    and tombstone deletion.
    """

    def __init__(self, initial_capacity: int = 8, max_load_factor: float = 0.66) -> None:
        """
        Initialize the hash map with a specified initial capacity and max load factor threshold.
        """
        raise NotImplementedError

    def put(self, key: str, val: Any) -> None:
        """
        Insert or update a key-value pair using linear probing.
        Recycles tombstone slots when inserting new keys.
        Rehashes when (size + tombstones) / capacity >= max_load_factor.
        """
        raise NotImplementedError

    def get(self, key: str) -> Any:
        """
        Retrieve the value associated with key.
        Raises KeyError if the key is not found.
        """
        raise NotImplementedError

    def contains(self, key: str) -> bool:
        """
        Return True if key exists in the map, False otherwise.
        """
        raise NotImplementedError

    def remove(self, key: str) -> None:
        """
        Delete key by placing a tombstone marker in its slot.
        Raises KeyError if key is not found.
        """
        raise NotImplementedError

    def size(self) -> int:
        """
        Return the number of active key-value pairs stored in the map.
        """
        raise NotImplementedError

    def capacity(self) -> int:
        """
        Return the total number of allocated bucket slots in the map.
        """
        raise NotImplementedError

    def load_factor(self) -> float:
        """
        Return the current active load factor: size / capacity.
        """
        raise NotImplementedError
