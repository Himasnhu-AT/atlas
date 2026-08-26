"""
Tests for bit manipulation primitives.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    compute_parity,
    extract_bitfield,
    pack_flags,
    sign_extend,
    unpack_flags,
)


class TestExtractBitfield(unittest.TestCase):
    def test_extract_basic(self):
        # 0b10110100 = 180, extract 4 bits from position 2 -> 0b1101 = 13
        self.assertEqual(extract_bitfield(0b10110100, 2, 4), 13)

    def test_extract_zero_length(self):
        self.assertEqual(extract_bitfield(0xFF, 4, 0), 0)

    def test_extract_single_bit(self):
        self.assertEqual(extract_bitfield(0b1000, 3, 1), 1)
        self.assertEqual(extract_bitfield(0b1000, 2, 1), 0)

    def test_extract_negative_input(self):
        # Two's complement representation in Python: -1 has all bits set
        self.assertEqual(extract_bitfield(-1, 0, 8), 255)
        self.assertEqual(extract_bitfield(-1, 4, 4), 15)

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            extract_bitfield(100, -1, 4)
        with self.assertRaises(ValueError):
            extract_bitfield(100, 2, -1)


class TestPackUnpackFlags(unittest.TestCase):
    def test_pack_empty(self):
        self.assertEqual(pack_flags([]), 0)

    def test_pack_single(self):
        self.assertEqual(pack_flags([True]), 1)
        self.assertEqual(pack_flags([False]), 0)

    def test_pack_multiple(self):
        # bits: 0: True, 1: False, 2: True, 3: True -> 1 + 4 + 8 = 13
        self.assertEqual(pack_flags([True, False, True, True]), 13)

    def test_unpack_basic(self):
        self.assertEqual(unpack_flags(13, 4), [True, False, True, True])

    def test_unpack_with_padding(self):
        self.assertEqual(unpack_flags(13, 6), [True, False, True, True, False, False])

    def test_unpack_zero_count(self):
        self.assertEqual(unpack_flags(13, 0), [])

    def test_unpack_invalid_count(self):
        with self.assertRaises(ValueError):
            unpack_flags(13, -1)

    def test_pack_unpack_roundtrip(self):
        flags = [True, False, True, False, True, True, False, True]
        packed = pack_flags(flags)
        unpacked = unpack_flags(packed, len(flags))
        self.assertEqual(flags, unpacked)


class TestSignExtend(unittest.TestCase):
    def test_positive_values_unchanged(self):
        self.assertEqual(sign_extend(0b0101, 4), 5)
        self.assertEqual(sign_extend(0x7F, 8), 127)
        self.assertEqual(sign_extend(0x7FFF, 16), 32767)

    def test_negative_values_extended(self):
        # 4-bit: 0b1111 is -1
        self.assertEqual(sign_extend(0b1111, 4), -1)
        # 4-bit: 0b1000 is -8
        self.assertEqual(sign_extend(0b1000, 4), -8)
        # 8-bit: 0xFF is -1
        self.assertEqual(sign_extend(0xFF, 8), -1)
        # 8-bit: 0x80 is -128
        self.assertEqual(sign_extend(0x80, 8), -128)
        # 16-bit: 0xFFFF is -1
        self.assertEqual(sign_extend(0xFFFF, 16), -1)
        # 16-bit: 0x8000 is -32768
        self.assertEqual(sign_extend(0x8000, 16), -32768)

    def test_single_bit_width(self):
        self.assertEqual(sign_extend(0, 1), 0)
        self.assertEqual(sign_extend(1, 1), -1)

    def test_raw_negative_input(self):
        self.assertEqual(sign_extend(-1, 8), -1)

    def test_invalid_bit_width(self):
        with self.assertRaises(ValueError):
            sign_extend(5, 0)
        with self.assertRaises(ValueError):
            sign_extend(5, -4)


class TestComputeParity(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(compute_parity(0), 0)

    def test_single_bits(self):
        self.assertEqual(compute_parity(1), 1)
        self.assertEqual(compute_parity(2), 1)
        self.assertEqual(compute_parity(4), 1)
        self.assertEqual(compute_parity(8), 1)

    def test_even_parity(self):
        # 0b0011 -> 2 bits
        self.assertEqual(compute_parity(3), 0)
        # 0b1010 -> 2 bits
        self.assertEqual(compute_parity(10), 0)
        # 0xFF -> 8 bits
        self.assertEqual(compute_parity(0xFF), 0)

    def test_odd_parity(self):
        # 0b0111 -> 3 bits
        self.assertEqual(compute_parity(7), 1)
        # 0b1011 -> 3 bits
        self.assertEqual(compute_parity(11), 1)
        # 0x1FF -> 9 bits
        self.assertEqual(compute_parity(0x1FF), 1)

    def test_negative_value_raises(self):
        with self.assertRaises(ValueError):
            compute_parity(-1)


if __name__ == '__main__':
    unittest.main()
