"""
Tests for move-ownership-buffer exercise.

Run with `python3 test.py`.
"""

from __future__ import annotations
import unittest
from solution import OwnedBuffer


class TestOwnedBufferInitialization(unittest.TestCase):
    def test_allocate_empty_buffer(self):
        buf = OwnedBuffer(16)
        self.assertEqual(buf.size(), 16)
        self.assertTrue(buf.is_valid())
        self.assertEqual(buf.read(0, 16), b"\x00" * 16)

    def test_allocate_with_initial_data(self):
        buf = OwnedBuffer(8, b"hello")
        self.assertEqual(buf.size(), 8)
        self.assertTrue(buf.is_valid())
        self.assertEqual(buf.read(0, 5), b"hello")
        self.assertEqual(buf.read(5, 3), b"\x00\x00\x00")

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            OwnedBuffer(-1)
        with self.assertRaises(TypeError):
            OwnedBuffer(10.5)  # type: ignore
        with self.assertRaises(ValueError):
            OwnedBuffer(4, b"exceeds_size")
        with self.assertRaises(TypeError):
            OwnedBuffer(4, "not_bytes")  # type: ignore


class TestOwnedBufferReadWrite(unittest.TestCase):
    def test_write_and_read(self):
        buf = OwnedBuffer(32)
        buf.write(4, b"systems")
        self.assertEqual(buf.read(4, 7), b"systems")
        self.assertEqual(buf.read(0, 4), b"\x00\x00\x00\x00")

    def test_out_of_bounds_write(self):
        buf = OwnedBuffer(10)
        with self.assertRaises(IndexError):
            buf.write(8, b"bytes_overflow")
        with self.assertRaises(IndexError):
            buf.write(-1, b"a")

    def test_out_of_bounds_read(self):
        buf = OwnedBuffer(10)
        with self.assertRaises(IndexError):
            buf.read(8, 5)
        with self.assertRaises(IndexError):
            buf.read(-1, 2)
        with self.assertRaises(IndexError):
            buf.read(2, -1)


class TestOwnedBufferClone(unittest.TestCase):
    def test_clone_independence(self):
        original = OwnedBuffer(16, b"immutable_seed")
        copy = original.clone()

        self.assertEqual(copy.size(), original.size())
        self.assertTrue(copy.is_valid())
        self.assertTrue(original.is_valid())

        # Mutate copy, ensure original is unchanged
        copy.write(0, b"mutated_buffer")
        self.assertEqual(copy.read(0, 14), b"mutated_buffer")
        self.assertEqual(original.read(0, 14), b"immutable_seed")

        # Mutate original, ensure copy is unchanged
        original.write(0, b"changed_origin")
        self.assertEqual(original.read(0, 14), b"changed_origin")
        self.assertEqual(copy.read(0, 14), b"mutated_buffer")


class TestOwnedBufferMove(unittest.TestCase):
    def test_move_transfers_ownership(self):
        source = OwnedBuffer(16, b"precious_payload")
        target = source.move_to()

        # Target holds the data
        self.assertTrue(target.is_valid())
        self.assertEqual(target.size(), 16)
        self.assertEqual(target.read(0, 16), b"precious_payload")

        # Source is invalidated
        self.assertFalse(source.is_valid())
        self.assertEqual(source.size(), 0)

    def test_moved_from_buffer_rejects_operations(self):
        source = OwnedBuffer(8, b"12345678")
        _ = source.move_to()

        with self.assertRaises(RuntimeError):
            source.write(0, b"fail")

        with self.assertRaises(RuntimeError):
            source.read(0, 4)

        with self.assertRaises(RuntimeError):
            source.clone()

        with self.assertRaises(RuntimeError):
            source.move_to()


if __name__ == "__main__":
    unittest.main(verbosity=2)
