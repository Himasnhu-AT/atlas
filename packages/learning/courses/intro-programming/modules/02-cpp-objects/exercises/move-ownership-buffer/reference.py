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
        if type(size) is not int:
            raise TypeError("size must be an integer")
        if size < 0:
            raise ValueError("size must be non-negative")

        self._buffer = bytearray(size)
        self._valid = True

        if initial_data is not None:
            if not isinstance(initial_data, (bytes, bytearray)):
                raise TypeError("initial_data must be bytes")
            if len(initial_data) > size:
                raise ValueError("initial_data exceeds buffer size")
            self._buffer[: len(initial_data)] = initial_data

    def size(self) -> int:
        """
        Return the size of the buffer in bytes. Returns 0 if buffer is invalid/moved-from.
        """
        if not self._valid:
            return 0
        return len(self._buffer)

    def is_valid(self) -> bool:
        """
        Return True if the buffer currently owns its allocated memory, False if moved-from.
        """
        return self._valid

    def clone(self) -> OwnedBuffer:
        """
        Perform a deep copy of the buffer, allocating new memory.

        Returns:
            A new OwnedBuffer with identical contents.

        Raises:
            RuntimeError: If this buffer has been moved from or is invalid.
        """
        if not self._valid:
            raise RuntimeError("Cannot clone invalid or moved-from buffer")
        return OwnedBuffer(len(self._buffer), bytes(self._buffer))

    def move_to(self) -> OwnedBuffer:
        """
        Transfer buffer ownership to a new OwnedBuffer instance.
        Marks this instance as invalid with size 0.

        Returns:
            A new OwnedBuffer instance holding the memory.

        Raises:
            RuntimeError: If this buffer has already been moved from or is invalid.
        """
        if not self._valid:
            raise RuntimeError("Cannot move from invalid or moved-from buffer")

        new_buf = OwnedBuffer.__new__(OwnedBuffer)
        new_buf._buffer = self._buffer
        new_buf._valid = True

        self._buffer = bytearray(0)
        self._valid = False
        return new_buf

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
        if not self._valid:
            raise RuntimeError("Cannot write to invalid or moved-from buffer")
        if type(offset) is not int:
            raise TypeError("offset must be an integer")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes")
        if offset < 0 or offset + len(data) > len(self._buffer):
            raise IndexError("Write out of bounds")

        self._buffer[offset : offset + len(data)] = data

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
        if not self._valid:
            raise RuntimeError("Cannot read from invalid or moved-from buffer")
        if type(offset) is not int:
            raise TypeError("offset must be an integer")
        if type(length) is not int:
            raise TypeError("length must be an integer")
        if offset < 0 or length < 0 or offset + length > len(self._buffer):
            raise IndexError("Read out of bounds")

        return bytes(self._buffer[offset : offset + length])
