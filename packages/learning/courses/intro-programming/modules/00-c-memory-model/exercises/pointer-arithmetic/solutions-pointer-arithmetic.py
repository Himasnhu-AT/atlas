"""
Pointer arithmetic and memory buffer operations: reference solution.
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
        if offset < 0 or offset > len(buffer):
            raise IndexError(f"Pointer offset {offset} out of bounds [0, {len(buffer)}]")
        self._buffer = buffer
        self._offset = offset

    @property
    def offset(self) -> int:
        """The current byte offset of the pointer."""
        return self._offset

    @property
    def buffer(self) -> bytearray:
        """The underlying bytearray buffer."""
        return self._buffer

    def deref(self) -> int:
        """
        Dereference the pointer to read the single byte at the current offset.

        Returns:
            Unsigned byte integer (0-255).

        Raises:
            IndexError: If the pointer is at or past the end of the buffer.
        """
        if self._offset >= len(self._buffer):
            raise IndexError("Cannot dereference out-of-bounds pointer")
        return self._buffer[self._offset]

    def write(self, val: int) -> None:
        """
        Write a single byte to the memory address at the current offset.

        Args:
            val: Byte value to write (truncated to 0-255).

        Raises:
            IndexError: If the pointer is at or past the end of the buffer.
        """
        if self._offset >= len(self._buffer):
            raise IndexError("Cannot write to out-of-bounds pointer")
        self._buffer[self._offset] = val & 0xFF

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
        new_offset = self._offset + offset
        if new_offset < 0 or new_offset > len(self._buffer):
            raise IndexError(f"Resulting offset {new_offset} out of bounds [0, {len(self._buffer)}]")
        return Pointer(self._buffer, new_offset)

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
        if not isinstance(other, Pointer) or self._buffer is not other._buffer:
            raise ValueError("Cannot diff pointers pointing to different buffers")
        return self._offset - other._offset


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
    if count < 0:
        raise ValueError("Count cannot be negative")
    if src.offset + count > len(src.buffer):
        raise IndexError("Source buffer overrun in memcpy")
    if dest.offset + count > len(dest.buffer):
        raise IndexError("Destination buffer overrun in memcpy")
    chunk = bytes(src.buffer[src.offset : src.offset + count])
    dest.buffer[dest.offset : dest.offset + count] = chunk


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
    buf = p.buffer
    off = p.offset
    length = 0
    while off + length < len(buf):
        if buf[off + length] == 0:
            return length
        length += 1
    raise IndexError("Unterminated string: reached end of buffer without null terminator")


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
    len1 = strlen(p1)
    len2 = strlen(p2)
    buf1 = p1.buffer
    buf2 = p2.buffer
    off1 = p1.offset
    off2 = p2.offset
    max_len = max(len1, len2)
    for i in range(max_len + 1):
        b1 = buf1[off1 + i] if (off1 + i < len(buf1) and i <= len1) else 0
        b2 = buf2[off2 + i] if (off2 + i < len(buf2) and i <= len2) else 0
        if b1 != b2:
            return b1 - b2
        if b1 == 0:
            break
    return 0
