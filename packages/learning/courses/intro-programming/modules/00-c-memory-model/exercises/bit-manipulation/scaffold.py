"""
Bit manipulation primitives.

Functions for extracting bitfields, packing boolean flags, sign-extending
fixed-width integers, and calculating bit parity.

Run `python3 test.py` to test your implementation.
"""

from __future__ import annotations


def extract_bitfield(val: int, start_bit: int, length: int) -> int:
    """
    Extract a contiguous bitfield of length bits starting at start_bit.

    Args:
        val: Integer source value.
        start_bit: Zero-indexed position of the least significant bit in the field.
        length: Number of bits to extract.

    Returns:
        The extracted unsigned integer value.

    Raises:
        ValueError: If start_bit < 0 or length < 0.
    """
    raise NotImplementedError


def pack_flags(flags: list[bool]) -> int:
    """
    Pack a list of boolean flags into a single integer.

    The flag at index i corresponds to bit position i (1 << i).

    Args:
        flags: List of booleans to pack.

    Returns:
        Integer representing the bitmask of set flags.
    """
    raise NotImplementedError


def unpack_flags(packed: int, count: int) -> list[bool]:
    """
    Unpack an integer bitmask into a list of boolean flags.

    Args:
        packed: The packed integer bitmask.
        count: Number of boolean flags to extract starting from bit 0.

    Returns:
        List of boolean values where index i corresponds to bit i.

    Raises:
        ValueError: If count < 0.
    """
    raise NotImplementedError


def sign_extend(val: int, bit_width: int) -> int:
    """
    Sign-extend a two's complement integer of bit_width bits to a Python integer.

    Args:
        val: Raw integer bits representing a two's complement value.
        bit_width: The bit width of the representation (e.g. 8 for signed char).

    Returns:
        Signed Python integer.

    Raises:
        ValueError: If bit_width <= 0.
    """
    raise NotImplementedError


def compute_parity(val: int) -> int:
    """
    Compute the parity bit for a non-negative integer.

    Args:
        val: Non-negative integer.

    Returns:
        1 if the number of set bits is odd, 0 if even.

    Raises:
        ValueError: If val < 0.
    """
    raise NotImplementedError
