"""
Move semantics and ownership transfer.

Implement OwnedBuffer representing an explicitly owned memory buffer with
deep copy cloning, move-to ownership transfer, and invalidation semantics.
"""

from __future__ import annotations
from typing import Optional


class OwnedBuffer:
    """
    Fixed-capacity byte buffer demonstrating explicit ownership and move semantics.
    """

    def __init__(self, size: int, initial_data: Optional[bytes] = None) -> None:
        """
        Allocate a buffer of the given size in bytes.

        Args:
            size: Non-negative buffer capacity in bytes.
            initial_data: Optional initial bytes to copy into the buffer.

        Raises:
            TypeError: If size is not an int or initial_data is not bytes.
            ValueError: If size < 0 or len(initial_data) > size.
        """
        raise NotImplementedError

    def size(self) -> int:
        """
        Return the size of the buffer in bytes. Returns 0 if buffer is invalid/moved-from.
        """
        raise NotImplementedError

    def is_valid(self) -> bool:
        """
        Return True if the buffer currently owns its allocated memory, False if moved-from.
        """
        raise NotImplementedError

    def clone(self) -> OwnedBuffer:
        """
        Perform a deep copy of the buffer, allocating new memory.

        Returns:
            A new OwnedBuffer with identical contents.

        Raises:
            RuntimeError: If this buffer has been moved from or is invalid.
        """
        raise NotImplementedError

    def move_to(self) -> OwnedBuffer:
        """
        Transfer buffer ownership to a new OwnedBuffer instance.
        Marks this instance as invalid with size 0.

        Returns:
            A new OwnedBuffer instance holding the memory.

        Raises:
            RuntimeError: If this buffer has already been moved from or is invalid.
        """
        raise NotImplementedError

    def write(self, offset: int, data: bytes) -> None:
        """
        Write bytes into the buffer at the specified offset.

        Args:
            offset: Starting byte index.
            data: Bytes to write.

        Raises:
            RuntimeError: If this buffer is invalid / moved-from.
            TypeError: If offset is not int or data is not bytes.
            IndexError: If offset < 0 or offset + len(data) > size().
        """
        raise NotImplementedError

    def read(self, offset: int, length: int) -> bytes:
        """
        Read a slice of bytes from the buffer.

        Args:
            offset: Starting byte index.
            length: Number of bytes to read.

        Returns:
            A bytes object of length `length`.

        Raises:
            RuntimeError: If this buffer is invalid / moved-from.
            TypeError: If offset or length is not int.
            IndexError: If offset < 0, length < 0, or offset + length > size().
        """
        raise NotImplementedError
