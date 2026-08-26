from __future__ import annotations

from typing import Any

_TOMBSTONE = object()


class OpenAddressingHashMap:
    """
    High-performance hash map implementing open addressing with linear probing
    and tombstone deletion.
    """

    def __init__(self, initial_capacity: int = 8, max_load_factor: float = 0.66) -> None:
        """
        Initialize the hash map with a specified initial capacity and max load factor threshold.
        """
        if initial_capacity < 1:
            initial_capacity = 8
        self._capacity = initial_capacity
        self._max_load_factor = max_load_factor
        self._table: list[Any] = [None] * self._capacity
        self._size = 0
        self._tombstones = 0

    def _rehash(self, new_capacity: int) -> None:
        old_table = self._table
        self._capacity = new_capacity
        self._table = [None] * new_capacity
        self._size = 0
        self._tombstones = 0
        for slot in old_table:
            if slot is not None and slot is not _TOMBSTONE:
                self.put(slot[0], slot[1])

    def put(self, key: str, val: Any) -> None:
        """
        Insert or update a key-value pair using linear probing.
        Recycles tombstone slots when inserting new keys.
        Rehashes when (size + tombstones) / capacity >= max_load_factor.
        """
        start_idx = hash(key) % self._capacity
        first_tombstone_idx: int | None = None
        empty_slot_idx: int | None = None
        existing_idx: int | None = None

        for i in range(self._capacity):
            idx = (start_idx + i) % self._capacity
            slot = self._table[idx]
            if slot is None:
                if empty_slot_idx is None:
                    empty_slot_idx = idx
                break
            if slot is _TOMBSTONE:
                if first_tombstone_idx is None:
                    first_tombstone_idx = idx
            elif slot[0] == key:
                existing_idx = idx
                break

        if existing_idx is not None:
            self._table[existing_idx] = (key, val)
            return

        if first_tombstone_idx is not None:
            self._table[first_tombstone_idx] = (key, val)
            self._tombstones -= 1
            self._size += 1
        elif empty_slot_idx is not None:
            self._table[empty_slot_idx] = (key, val)
            self._size += 1
        else:
            self._rehash(self._capacity * 2)
            self.put(key, val)
            return

        if (self._size + self._tombstones) / self._capacity >= self._max_load_factor:
            self._rehash(self._capacity * 2)

    def get(self, key: str) -> Any:
        """
        Retrieve the value associated with key.
        Raises KeyError if the key is not found.
        """
        start_idx = hash(key) % self._capacity
        for i in range(self._capacity):
            idx = (start_idx + i) % self._capacity
            slot = self._table[idx]
            if slot is None:
                raise KeyError(key)
            if slot is _TOMBSTONE:
                continue
            if slot[0] == key:
                return slot[1]
        raise KeyError(key)

    def contains(self, key: str) -> bool:
        """
        Return True if key exists in the map, False otherwise.
        """
        start_idx = hash(key) % self._capacity
        for i in range(self._capacity):
            idx = (start_idx + i) % self._capacity
            slot = self._table[idx]
            if slot is None:
                return False
            if slot is _TOMBSTONE:
                continue
            if slot[0] == key:
                return True
        return False

    def remove(self, key: str) -> None:
        """
        Delete key by placing a tombstone marker in its slot.
        Raises KeyError if key is not found.
        """
        start_idx = hash(key) % self._capacity
        for i in range(self._capacity):
            idx = (start_idx + i) % self._capacity
            slot = self._table[idx]
            if slot is None:
                raise KeyError(key)
            if slot is _TOMBSTONE:
                continue
            if slot[0] == key:
                self._table[idx] = _TOMBSTONE
                self._size -= 1
                self._tombstones += 1
                return
        raise KeyError(key)

    def size(self) -> int:
        """
        Return the number of active key-value pairs stored in the map.
        """
        return self._size

    def capacity(self) -> int:
        """
        Return the total number of allocated bucket slots in the map.
        """
        return self._capacity

    def load_factor(self) -> float:
        """
        Return the current active load factor: size / capacity.
        """
        return self._size / self._capacity
