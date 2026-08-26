"""
Smart pointers and reference count management.

Implement ControlBlock, SharedPtr, and WeakPtr simulating shared ownership,
atomic reference counting, non-owning observers, and expiration cycles.
"""

from __future__ import annotations
from typing import Any, Optional


class ControlBlock:
    """
    Control block tracking managed value, strong use_count, and weak_count.
    """

    def __init__(self, value: Any = None, use_count: int = 1, weak_count: int = 0) -> None:
        """
        Initialize a control block.

        Args:
            value: Managed resource value.
            use_count: Initial strong reference count.
            weak_count: Initial weak reference count.
        """
        self.value = value
        self.use_count = use_count
        self.weak_count = weak_count


class SharedPtr:
    """
    Reference-counted smart pointer managing shared ownership of a resource.
    """

    def __init__(self, value: Any = None, control_block: Optional[ControlBlock] = None) -> None:
        """
        Initialize a SharedPtr managing a new value or attaching to an existing control block.

        Args:
            value: Value to manage if creating a new control block.
            control_block: Existing control block to attach to.
        """
        if control_block is not None:
            self._cb: Optional[ControlBlock] = control_block
        elif value is not None:
            self._cb = ControlBlock(value=value, use_count=1, weak_count=0)
        else:
            self._cb = None

    def get(self) -> Any:
        """
        Return the managed value.

        Raises:
            RuntimeError: If the pointer is null, reset, or expired.
        """
        if self._cb is None or self._cb.use_count == 0:
            raise RuntimeError("Pointer is null or expired")
        return self._cb.value

    def use_count(self) -> int:
        """
        Return the current strong reference count. Returns 0 if null or reset.
        """
        if self._cb is None:
            return 0
        return self._cb.use_count

    def clone(self) -> SharedPtr:
        """
        Create a new SharedPtr sharing ownership, incrementing use_count.

        Returns:
            A new SharedPtr sharing the control block.

        Raises:
            RuntimeError: If this SharedPtr is null or reset.
        """
        if self._cb is None or self._cb.use_count == 0:
            raise RuntimeError("Cannot clone null or expired SharedPtr")
        self._cb.use_count += 1
        return SharedPtr(control_block=self._cb)

    def reset(self) -> None:
        """
        Release ownership of the managed resource. Decrements use_count.
        If use_count reaches 0, clears the managed value.
        """
        if self._cb is not None:
            self._cb.use_count -= 1
            if self._cb.use_count == 0:
                self._cb.value = None
            self._cb = None

    def to_weak(self) -> WeakPtr:
        """
        Create a non-owning WeakPtr observer from this SharedPtr.

        Returns:
            A WeakPtr observing the control block.

        Raises:
            RuntimeError: If this SharedPtr is null or reset.
        """
        if self._cb is None or self._cb.use_count == 0:
            raise RuntimeError("Cannot create WeakPtr from null or expired SharedPtr")
        self._cb.weak_count += 1
        return WeakPtr(control_block=self._cb)


class WeakPtr:
    """
    Non-owning observer of a SharedPtr-managed resource.
    """

    def __init__(self, control_block: Optional[ControlBlock] = None) -> None:
        """
        Initialize a WeakPtr observing the given control block.

        Args:
            control_block: Optional control block to observe.
        """
        self._cb: Optional[ControlBlock] = control_block

    def use_count(self) -> int:
        """
        Return the strong use_count of the observed resource. Returns 0 if expired or null.
        """
        if self._cb is None:
            return 0
        return self._cb.use_count

    def expired(self) -> bool:
        """
        Return True if use_count is 0 or control block is None, False otherwise.
        """
        if self._cb is None:
            return True
        return self._cb.use_count == 0

    def lock(self) -> Optional[SharedPtr]:
        """
        Acquire a SharedPtr if the resource is still alive.

        Returns:
            A new SharedPtr if use_count > 0, or None if expired.
        """
        if self.expired() or self._cb is None:
            return None
        self._cb.use_count += 1
        return SharedPtr(control_block=self._cb)
