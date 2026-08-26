"""
Support library for intro-programming course.

Provides zero-dependency memory inspection, bitwise utilities, and deterministic
data fixtures for exercises simulating low-level systems in C, C++, and Python.
"""

from __future__ import annotations

import struct
from typing import List, Tuple, Dict, Any, Optional


class VirtualMemory:
    """
    Simulated linear byte address space for memory management and pointer exercises.
    """

    def __init__(self, size: int = 1024, base_address: int = 0x1000):
        self.size = size
        self.base_address = base_address
        self.buffer = bytearray(size)

    def is_valid_address(self, addr: int, length: int = 1) -> bool:
        return self.base_address <= addr and (addr + length) <= (self.base_address + self.size)

    def offset(self, addr: int) -> int:
        if not self.is_valid_address(addr, 1):
            raise IndexError(f"Address {hex(addr)} out of bounds [{hex(self.base_address)}, {hex(self.base_address + self.size)})")
        return addr - self.base_address

    def read_byte(self, addr: int) -> int:
        return self.buffer[self.offset(addr)]

    def write_byte(self, addr: int, val: int) -> None:
        self.buffer[self.offset(addr)] = val & 0xFF

    def read_bytes(self, addr: int, length: int) -> bytes:
        if not self.is_valid_address(addr, length):
            raise IndexError(f"Address range [{hex(addr)}, {hex(addr + length)}) out of bounds")
        off = self.offset(addr)
        return bytes(self.buffer[off : off + length])

    def write_bytes(self, addr: int, data: bytes) -> None:
        if not self.is_valid_address(addr, len(data)):
            raise IndexError(f"Address range [{hex(addr)}, {hex(addr + len(data))}) out of bounds")
        off = self.offset(addr)
        self.buffer[off : off + len(data)] = data

    def read_u32_le(self, addr: int) -> int:
        return struct.unpack("<I", self.read_bytes(addr, 4))[0]

    def write_u32_le(self, addr: int, val: int) -> None:
        self.write_bytes(addr, struct.pack("<I", val & 0xFFFFFFFF))


def format_hex_dump(data: bytes, base_address: int = 0, bytes_per_line: int = 16) -> str:
    """Format bytes as standard hex dump lines."""
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_parts = " ".join(f"{b:02x}" for b in chunk)
        ascii_parts = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{base_address + i:08x}  {hex_parts:<{bytes_per_line * 3}}  |{ascii_parts}|")
    return "\n".join(lines)


def align_up(offset: int, alignment: int) -> int:
    """Align an offset upward to a multiple of alignment."""
    if alignment <= 0 or (alignment & (alignment - 1)) != 0:
        raise ValueError("Alignment must be a power of 2")
    return (offset + alignment - 1) & ~(alignment - 1)
