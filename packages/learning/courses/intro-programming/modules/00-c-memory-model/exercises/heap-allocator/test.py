"""
Tests for free-list heap memory allocator.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    Block,
    FreeListAllocator,
)


class TestBlock(unittest.TestCase):
    def test_block_init(self):
        b = Block(offset=0, size=64, is_free=True)
        self.assertEqual(b.offset, 0)
        self.assertEqual(b.size, 64)
        self.assertTrue(b.is_free)
        self.assertIsNone(b.next)
        self.assertIsNone(b.prev)


class TestFreeListAllocator(unittest.TestCase):
    def test_initial_state(self):
        alloc = FreeListAllocator(total_bytes=1024, alignment=8)
        self.assertEqual(alloc.get_block_count(), 1)
        self.assertEqual(alloc.get_free_bytes(), 1024)

    def test_invalid_init(self):
        with self.assertRaises(ValueError):
            FreeListAllocator(total_bytes=0)
        with self.assertRaises(ValueError):
            FreeListAllocator(alignment=3)  # Not power of 2
        with self.assertRaises(ValueError):
            FreeListAllocator(total_bytes=10, alignment=8)  # total_bytes < 16

    def test_malloc_single(self):
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        # Header is 8 bytes, payload requested is 16 -> total block size 24
        addr = alloc.malloc(16)
        self.assertEqual(addr, 8)  # offset 0 + header 8
        self.assertTrue(alloc.is_allocated(addr))
        self.assertEqual(alloc.get_block_count(), 2)
        # Remaining free block: 256 - 24 = 232
        self.assertEqual(alloc.get_free_bytes(), 232)

    def test_malloc_alignment(self):
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        # Requesting 5 bytes will align to 8 bytes payload -> total block size 16 (8 header + 8 payload)
        addr1 = alloc.malloc(5)
        self.assertEqual(addr1, 8)

        addr2 = alloc.malloc(12)  # 12 aligns to 16 bytes payload -> block size 24 (8 header + 16 payload)
        self.assertEqual(addr2, 24)  # 16 + 8 header = 24

        self.assertTrue(alloc.is_allocated(addr1))
        self.assertTrue(alloc.is_allocated(addr2))

    def test_malloc_invalid_size(self):
        alloc = FreeListAllocator(total_bytes=128)
        with self.assertRaises(ValueError):
            alloc.malloc(0)
        with self.assertRaises(ValueError):
            alloc.malloc(-10)

    def test_out_of_memory(self):
        alloc = FreeListAllocator(total_bytes=64, alignment=8)
        # Allocate entire space
        alloc.malloc(48)  # 8 header + 48 payload = 56 bytes, remainder = 8 < 16 so whole 64 allocated
        with self.assertRaises(MemoryError):
            alloc.malloc(16)

    def test_free_and_coalesce_single(self):
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        addr = alloc.malloc(32)  # 8 header + 32 payload = 40 bytes
        self.assertEqual(alloc.get_block_count(), 2)

        alloc.free(addr)
        self.assertFalse(alloc.is_allocated(addr))
        self.assertEqual(alloc.get_block_count(), 1)
        self.assertEqual(alloc.get_free_bytes(), 256)

    def test_coalesce_middle_block(self):
        # Allocate 3 blocks
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        a1 = alloc.malloc(16)  # block 1: 0..24
        a2 = alloc.malloc(16)  # block 2: 24..48
        a3 = alloc.malloc(16)  # block 3: 48..72
        # Remaining block 4: 72..256
        self.assertEqual(alloc.get_block_count(), 4)

        # Free a1 (now block 1 is free, block 2 allocated, block 3 allocated, block 4 free)
        alloc.free(a1)
        self.assertEqual(alloc.get_block_count(), 4)

        # Free a3 (now block 3 coalesces with block 4)
        alloc.free(a3)
        self.assertEqual(alloc.get_block_count(), 3)

        # Free a2 (now block 2 coalesces with block 1 and block 3+4 -> all merged into 1 block)
        alloc.free(a2)
        self.assertEqual(alloc.get_block_count(), 1)
        self.assertEqual(alloc.get_free_bytes(), 256)

    def test_invalid_free_and_double_free(self):
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        addr = alloc.malloc(16)

        with self.assertRaises(ValueError):
            alloc.free(addr + 4)  # Invalid pointer offset

        with self.assertRaises(ValueError):
            alloc.free(999)  # Nonexistent address

        alloc.free(addr)
        with self.assertRaises(ValueError):
            alloc.free(addr)  # Double free

    def test_first_fit_reuse(self):
        alloc = FreeListAllocator(total_bytes=256, alignment=8)
        a1 = alloc.malloc(32)  # 40 bytes: offset 0
        a2 = alloc.malloc(32)  # 40 bytes: offset 40
        alloc.free(a1)          # Free first 40 bytes

        # New allocation fitting in 40 bytes should reuse slot 0
        a3 = alloc.malloc(16)  # 24 bytes: should take offset 0, splitting the 40-byte block
        self.assertEqual(a3, 8)
        self.assertTrue(alloc.is_allocated(a3))
        self.assertTrue(alloc.is_allocated(a2))


if __name__ == '__main__':
    unittest.main()
