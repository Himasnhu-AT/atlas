"""
Pointer arithmetic and memory buffer operations.

Simulates raw memory pointers over linear byte buffers, demonstrating
dereferencing, pointer addition and difference, bounds checking, and C-style
string operations.

Run `python3 test.py` to test your implementation.
"""

from __future__ import annotations


class Pointer:
    """
    A pointer into a contiguous bytearray buffer.
    """

    def __init__(self, buffer: bytearray, offset: int = 0) -> None:
        """
        Initialize a pointer to a specific offset in buffer.

        Args:
            buffer: The backing bytearray.
            offset: The byte index into the buffer (default 0).

        Raises:
            IndexError: If offset is negative or exceeds len(buffer).
        """
        raise NotImplementedError

    @property
    def offset(self) -> int:
        """The current byte offset of the pointer."""
        raise NotImplementedError

    @property
    def buffer(self) -> bytearray:
        """The underlying bytearray buffer."""
        raise NotImplementedError

    def deref(self) -> int:
        """
        Dereference the pointer to read the single byte at the current offset.

        Returns:
            Unsigned byte integer (0-255).

        Raises:
            IndexError: If the pointer is at or past the end of the buffer.
        """
        raise NotImplementedError

    def write(self, val: int) -> None:
        """
        Write a single byte to the memory address at the current offset.

        Args:
            val: Byte value to write (truncated to 0-255).

        Raises:
            IndexError: If the pointer is at or past the end of the buffer.
        """
        raise NotImplementedError

    def add(self, offset: int) -> Pointer:
        """
        Create a new Pointer displaced by offset bytes.

        Args:
            offset: Number of bytes to advance (positive or negative).

        Returns:
            A new Pointer instance pointing to the displaced offset.

        Raises:
            IndexError: If the resulting offset is out of bounds [0, len(buffer)].
        """
        raise NotImplementedError

    def diff(self, other: Pointer) -> int:
        """
        Compute pointer difference (self - other) in bytes.

        Args:
            other: Pointer into the same buffer.

        Returns:
            Difference in bytes (self.offset - other.offset).

        Raises:
            ValueError: If other does not point to the same buffer.
        """
        raise NotImplementedError


def memcpy(dest: Pointer, src: Pointer, count: int) -> None:
    """
    Copy count bytes from src pointer to dest pointer.

    Args:
        dest: Destination pointer.
        src: Source pointer.
        count: Number of bytes to copy.

    Raises:
        ValueError: If count is negative.
        IndexError: If copy range exceeds source or destination buffer bounds.
    """
    raise NotImplementedError


def strlen(p: Pointer) -> int:
    """
    Calculate the length of a null-terminated string starting at pointer p.

    Args:
        p: Pointer to the start of a null-terminated string.

    Returns:
        Number of bytes preceding the terminating 0x00 null byte.

    Raises:
        IndexError: If the buffer ends before encountering a 0x00 null byte.
    """
    raise NotImplementedError


def strcmp(p1: Pointer, p2: Pointer) -> int:
    """
    Compare two null-terminated strings lexicographically.

    Args:
        p1: Pointer to the first string.
        p2: Pointer to the second string.

    Returns:
        Negative integer if p1 < p2, zero if p1 == p2, positive integer if p1 > p2.

    Raises:
        IndexError: If either string is not null-terminated before buffer end.
    """
    raise NotImplementedError
