"""
Free-list heap memory allocator.

Simulates manual memory management, first-fit allocation, block header
bookkeeping, block splitting, and immediate bidirectional coalescing.

Run `python3 test.py` to test your implementation.
"""

from __future__ import annotations

from typing import Optional


class Block:
    """
    Node in the memory block list representing an allocated or free memory chunk.
    """

    def __init__(
        self,
        offset: int,
        size: int,
        is_free: bool = True,
        next: Optional[Block] = None,
        prev: Optional[Block] = None,
    ) -> None:
        """
        Initialize a memory block.

        Args:
            offset: Byte offset where this block starts in the memory pool.
            size: Total size of the block in bytes (including 8-byte header).
            is_free: True if block is available for allocation, False if allocated.
            next: Pointer to next contiguous block in the heap.
            prev: Pointer to previous contiguous block in the heap.
        """
        raise NotImplementedError


class FreeListAllocator:
    """
    Explicit free-list memory allocator with first-fit strategy and coalescing.
    """

    HEADER_SIZE: int = 8

    def __init__(self, total_bytes: int = 1024, alignment: int = 8) -> None:
        """
        Initialize the allocator pool.

        Args:
            total_bytes: Total capacity of the memory pool in bytes.
            alignment: Byte alignment boundary for allocated payloads (must be power of 2).

        Raises:
            ValueError: If total_bytes < alignment + HEADER_SIZE or alignment is not a power of 2.
        """
        raise NotImplementedError

    def malloc(self, size: int) -> int:
        """
        Allocate a memory block with at least size bytes of payload.

        Payload is padded to the allocator's alignment boundary and preceded by
        an 8-byte header.

        Args:
            size: Requested payload size in bytes.

        Returns:
            The byte address (offset) of the allocated payload (block.offset + HEADER_SIZE).

        Raises:
            ValueError: If size <= 0.
            MemoryError: If no contiguous free block can satisfy the request.
        """
        raise NotImplementedError

    def free(self, address: int) -> None:
        """
        Free a previously allocated block and coalesce with adjacent free blocks.

        Args:
            address: The payload address returned by a prior malloc() call.

        Raises:
            ValueError: If address does not match an active allocated block or is already free.
        """
        raise NotImplementedError

    def is_allocated(self, address: int) -> bool:
        """
        Check if an address corresponds to an active allocated payload.

        Args:
            address: The payload address to inspect.

        Returns:
            True if address is an active allocated block payload, False otherwise.
        """
        raise NotImplementedError

    def get_free_bytes(self) -> int:
        """
        Calculate total free bytes remaining in the allocator pool.

        Returns:
            Sum of sizes of all currently free blocks.
        """
        raise NotImplementedError

    def get_block_count(self) -> int:
        """
        Count total number of blocks (both free and allocated) in the heap list.

        Returns:
            Total block count.
        """
        raise NotImplementedError
