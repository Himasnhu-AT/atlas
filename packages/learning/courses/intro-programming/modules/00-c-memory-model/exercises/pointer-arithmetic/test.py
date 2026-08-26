"""
Tests for pointer arithmetic and buffer operations.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    Pointer,
    memcpy,
    strcmp,
    strlen,
)


class TestPointerBasics(unittest.TestCase):
    def test_init_and_properties(self):
        buf = bytearray(b"abcdef")
        p = Pointer(buf, 2)
        self.assertEqual(p.offset, 2)
        self.assertIs(p.buffer, buf)
        self.assertEqual(p.deref(), ord('c'))

    def test_init_bounds(self):
        buf = bytearray(10)
        Pointer(buf, 0)
        Pointer(buf, 10)
        with self.assertRaises(IndexError):
            Pointer(buf, -1)
        with self.assertRaises(IndexError):
            Pointer(buf, 11)

    def test_write_and_deref(self):
        buf = bytearray(4)
        p = Pointer(buf, 1)
        p.write(0x42)
        self.assertEqual(p.deref(), 0x42)
        self.assertEqual(buf[1], 0x42)

    def test_deref_past_end(self):
        buf = bytearray(4)
        p = Pointer(buf, 4)
        with self.assertRaises(IndexError):
            p.deref()
        with self.assertRaises(IndexError):
            p.write(1)

    def test_pointer_arithmetic(self):
        buf = bytearray(b"hello world")
        p = Pointer(buf, 0)
        p_next = p.add(6)
        self.assertEqual(p_next.offset, 6)
        self.assertEqual(p_next.deref(), ord('w'))

        p_back = p_next.add(-1)
        self.assertEqual(p_back.offset, 5)
        self.assertEqual(p_back.deref(), ord(' '))

    def test_pointer_arithmetic_overflow(self):
        buf = bytearray(5)
        p = Pointer(buf, 3)
        with self.assertRaises(IndexError):
            p.add(3)
        with self.assertRaises(IndexError):
            p.add(-4)

    def test_pointer_diff(self):
        buf = bytearray(16)
        p1 = Pointer(buf, 10)
        p2 = Pointer(buf, 4)
        self.assertEqual(p1.diff(p2), 6)
        self.assertEqual(p2.diff(p1), -6)

    def test_pointer_diff_different_buffers(self):
        buf1 = bytearray(10)
        buf2 = bytearray(10)
        p1 = Pointer(buf1, 2)
        p2 = Pointer(buf2, 2)
        with self.assertRaises(ValueError):
            p1.diff(p2)


class TestMemcpy(unittest.TestCase):
    def test_basic_copy(self):
        src_buf = bytearray(b"DATA_TO_COPY")
        dest_buf = bytearray(20)
        src = Pointer(src_buf, 0)
        dest = Pointer(dest_buf, 4)
        memcpy(dest, src, len(src_buf))
        self.assertEqual(dest_buf[4:4 + len(src_buf)], b"DATA_TO_COPY")

    def test_overlapping_copy_forward(self):
        buf = bytearray(b"0123456789")
        src = Pointer(buf, 0)
        dest = Pointer(buf, 2)
        memcpy(dest, src, 5)
        self.assertEqual(bytes(buf), b"0101234789")

    def test_negative_count(self):
        buf = bytearray(10)
        p = Pointer(buf, 0)
        with self.assertRaises(ValueError):
            memcpy(p, p, -1)

    def test_buffer_bounds_violation(self):
        src_buf = bytearray(5)
        dest_buf = bytearray(5)
        src = Pointer(src_buf, 2)
        dest = Pointer(dest_buf, 0)
        with self.assertRaises(IndexError):
            memcpy(dest, src, 4)


class TestStrlenAndStrcmp(unittest.TestCase):
    def test_strlen_basic(self):
        buf = bytearray(b"atlas\x00extra")
        p = Pointer(buf, 0)
        self.assertEqual(strlen(p), 5)

        p_offset = Pointer(buf, 2)
        self.assertEqual(strlen(p_offset), 3)

    def test_strlen_empty_string(self):
        buf = bytearray(b"\x00hello")
        p = Pointer(buf, 0)
        self.assertEqual(strlen(p), 0)

    def test_strlen_unterminated(self):
        buf = bytearray(b"no_null_byte_here")
        p = Pointer(buf, 0)
        with self.assertRaises(IndexError):
            strlen(p)

    def test_strcmp_equal(self):
        buf = bytearray(b"test\x00test\x00")
        p1 = Pointer(buf, 0)
        p2 = Pointer(buf, 5)
        self.assertEqual(strcmp(p1, p2), 0)

    def test_strcmp_less_greater(self):
        buf = bytearray(b"apple\x00apply\x00")
        p1 = Pointer(buf, 0)
        p2 = Pointer(buf, 6)
        self.assertLess(strcmp(p1, p2), 0)
        self.assertGreater(strcmp(p2, p1), 0)

    def test_strcmp_prefix(self):
        buf = bytearray(b"cat\x00cats\x00")
        p1 = Pointer(buf, 0)
        p2 = Pointer(buf, 4)
        self.assertLess(strcmp(p1, p2), 0)
        self.assertGreater(strcmp(p2, p1), 0)

    def test_strcmp_unterminated_raises(self):
        buf1 = bytearray(b"unterminated")
        buf2 = bytearray(b"valid\x00")
        p1 = Pointer(buf1, 0)
        p2 = Pointer(buf2, 0)
        with self.assertRaises(IndexError):
            strcmp(p1, p2)


if __name__ == '__main__':
    unittest.main()
