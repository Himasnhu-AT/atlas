"""
Free-list heap memory allocator: reference solution.
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
        self.offset = offset
        self.size = size
        self.is_free = is_free
        self.next = next
        self.prev = prev


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
        if total_bytes <= 0 or alignment <= 0:
            raise ValueError("total_bytes and alignment must be positive")
        if (alignment & (alignment - 1)) != 0:
            raise ValueError("alignment must be a power of 2")
        if total_bytes < alignment + self.HEADER_SIZE:
            raise ValueError(f"total_bytes must be at least {alignment + self.HEADER_SIZE}")

        self.total_bytes = total_bytes
        self.alignment = alignment
        self.head: Block = Block(offset=0, size=total_bytes, is_free=True)

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
        if size <= 0:
            raise ValueError("Allocation size must be positive")

        # Calculate aligned payload size
        aligned_payload = ((size + self.alignment - 1) // self.alignment) * self.alignment
        total_needed = self.HEADER_SIZE + aligned_payload

        # First-fit search
        curr: Optional[Block] = self.head
        while curr is not None:
            if curr.is_free and curr.size >= total_needed:
                # Check if block should be split
                min_split_size = self.HEADER_SIZE + self.alignment
                if curr.size - total_needed >= min_split_size:
                    remainder = curr.size - total_needed
                    new_block = Block(
                        offset=curr.offset + total_needed,
                        size=remainder,
                        is_free=True,
                        next=curr.next,
                        prev=curr,
                    )
                    if curr.next is not None:
                        curr.next.prev = new_block
                    curr.next = new_block
                    curr.size = total_needed

                curr.is_free = False
                return curr.offset + self.HEADER_SIZE

            curr = curr.next

        raise MemoryError(f"Out of memory: cannot allocate {size} bytes")

    def free(self, address: int) -> None:
        """
        Free a previously allocated block and coalesce with adjacent free blocks.

        Args:
            address: The payload address returned by a prior malloc() call.

        Raises:
            ValueError: If address does not match an active allocated block or is already free.
        """
        block_offset = address - self.HEADER_SIZE
        curr: Optional[Block] = self.head
        target: Optional[Block] = None

        while curr is not None:
            if curr.offset == block_offset:
                target = curr
                break
            curr = curr.next

        if target is None or target.is_free:
            raise ValueError(f"Invalid free or double free at address {address}")

        target.is_free = True

        # Coalesce with next block if free
        if target.next is not None and target.next.is_free:
            target.size += target.next.size
            target.next = target.next.next
            if target.next is not None:
                target.next.prev = target

        # Coalesce with previous block if free
        if target.prev is not None and target.prev.is_free:
            prev_block = target.prev
            prev_block.size += target.size
            prev_block.next = target.next
            if target.next is not None:
                target.next.prev = prev_block

    def is_allocated(self, address: int) -> bool:
        """
        Check if an address corresponds to an active allocated payload.

        Args:
            address: The payload address to inspect.

        Returns:
            True if address is an active allocated block payload, False otherwise.
        """
        block_offset = address - self.HEADER_SIZE
        curr: Optional[Block] = self.head
        while curr is not None:
            if curr.offset == block_offset:
                return not curr.is_free
            curr = curr.next
        return False

    def get_free_bytes(self) -> int:
        """
        Calculate total free bytes remaining in the allocator pool.

        Returns:
            Sum of sizes of all currently free blocks.
        """
        total = 0
        curr: Optional[Block] = self.head
        while curr is not None:
            if curr.is_free:
                total += curr.size
            curr = curr.next
        return total

    def get_block_count(self) -> int:
        """
        Count total number of blocks (both free and allocated) in the heap list.

        Returns:
            Total block count.
        """
        count = 0
        curr: Optional[Block] = self.head
        while curr is not None:
            count += 1
            curr = curr.next
        return count
