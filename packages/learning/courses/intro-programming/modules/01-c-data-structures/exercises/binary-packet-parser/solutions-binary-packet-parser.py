from __future__ import annotations

import struct
from typing import Any

MAGIC_BYTES = 0xAA55
HEADER_SIZE = 10
CHECKSUM_SIZE = 2
MIN_PACKET_SIZE = HEADER_SIZE + CHECKSUM_SIZE


def serialize_packet(packet_type: int, flags: int, seq_id: int, payload: bytes) -> bytes:
    """
    Serialize a packet into binary wire format.

    Header (10 bytes):
      - Magic: 2 bytes (0xAA55, big-endian)
      - Type: 1 byte (uint8)
      - Flags: 1 byte (uint8)
      - Seq ID: 4 bytes (uint32, big-endian)
      - Payload Length: 2 bytes (uint16, big-endian)
    Payload: N bytes
    Checksum: 2 bytes (uint16, big-endian)
      Calculated as the sum of all preceding bytes (header + payload) modulo 65536.

    Returns the complete packet bytes.
    """
    payload_len = len(payload)
    if payload_len > 0xFFFF:
        raise ValueError(f"Payload length {payload_len} exceeds 16-bit unsigned limit")

    header = struct.pack(
        ">HBBIH",
        MAGIC_BYTES,
        packet_type & 0xFF,
        flags & 0xFF,
        seq_id & 0xFFFFFFFF,
        payload_len,
    )
    preceding = header + payload
    checksum = sum(preceding) % 65536
    return preceding + struct.pack(">H", checksum)


def deserialize_packet(data: bytes) -> dict[str, Any]:
    """
    Parse and validate a binary packet from raw bytes.

    Validates:
      - Minimum length (at least 12 bytes)
      - Magic bytes (must be 0xAA55)
      - Total length matches header length (10 + payload_length + 2 == len(data))
      - Checksum matches sum of preceding bytes modulo 65536

    Returns dict:
      {"type": int, "flags": int, "seq_id": int, "payload": bytes}

    Raises ValueError if:
      - data is shorter than minimum packet length (12 bytes)
      - Magic bytes do not equal 0xAA55
      - Buffer is truncated or exceeds declared payload length
      - Checksum verification fails
    """
    if len(data) < MIN_PACKET_SIZE:
        raise ValueError(
            f"Packet length {len(data)} is less than minimum {MIN_PACKET_SIZE} bytes"
        )

    magic, packet_type, flags, seq_id, payload_len = struct.unpack_from(">HBBIH", data, 0)
    if magic != MAGIC_BYTES:
        raise ValueError(
            f"Invalid magic bytes 0x{magic:04X}, expected 0x{MAGIC_BYTES:04X}"
        )

    expected_total_len = HEADER_SIZE + payload_len + CHECKSUM_SIZE
    if len(data) != expected_total_len:
        raise ValueError(
            f"Packet length {len(data)} does not match expected length {expected_total_len} "
            f"(header {HEADER_SIZE} + payload {payload_len} + checksum {CHECKSUM_SIZE})"
        )

    payload = data[HEADER_SIZE : HEADER_SIZE + payload_len]
    (actual_checksum,) = struct.unpack_from(">H", data, HEADER_SIZE + payload_len)

    computed_checksum = sum(data[:-CHECKSUM_SIZE]) % 65536
    if actual_checksum != computed_checksum:
        raise ValueError(
            f"Checksum mismatch: expected 0x{computed_checksum:04X}, got 0x{actual_checksum:04X}"
        )

    return {
        "type": packet_type,
        "flags": flags,
        "seq_id": seq_id,
        "payload": payload,
    }
