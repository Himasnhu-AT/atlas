from __future__ import annotations

from typing import Any


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
    raise NotImplementedError


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
    raise NotImplementedError
