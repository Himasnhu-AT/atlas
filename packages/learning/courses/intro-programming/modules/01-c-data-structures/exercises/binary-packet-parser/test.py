from __future__ import annotations

import unittest
from solution import serialize_packet, deserialize_packet


class TestBinaryPacketParser(unittest.TestCase):
    def test_round_trip_empty_payload(self):
        packet = serialize_packet(packet_type=1, flags=0, seq_id=100, payload=b"")
        self.assertEqual(len(packet), 12)  # 10 bytes header + 0 bytes payload + 2 bytes checksum
        parsed = deserialize_packet(packet)
        self.assertEqual(parsed["type"], 1)
        self.assertEqual(parsed["flags"], 0)
        self.assertEqual(parsed["seq_id"], 100)
        self.assertEqual(parsed["payload"], b"")

    def test_round_trip_with_payload(self):
        payload = b"GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n"
        packet = serialize_packet(
            packet_type=5,
            flags=0x80,
            seq_id=4294967295,  # Max uint32
            payload=payload,
        )
        self.assertEqual(len(packet), 10 + len(payload) + 2)

        parsed = deserialize_packet(packet)
        self.assertEqual(parsed["type"], 5)
        self.assertEqual(parsed["flags"], 0x80)
        self.assertEqual(parsed["seq_id"], 4294967295)
        self.assertEqual(parsed["payload"], payload)

    def test_truncated_buffer_shorter_than_header(self):
        with self.assertRaises(ValueError):
            deserialize_packet(b"")
        with self.assertRaises(ValueError):
            deserialize_packet(b"\xaa\x55\x01\x00")
        with self.assertRaises(ValueError):
            deserialize_packet(b"\xaa\x55\x01\x00\x00\x00\x00\x01\x00\x05")

    def test_wrong_magic_bytes(self):
        # Correctly constructed packet
        packet = bytearray(serialize_packet(1, 0, 1, b"hello"))
        # Corrupt magic byte
        packet[0] = 0xBB
        with self.assertRaises(ValueError):
            deserialize_packet(bytes(packet))

    def test_payload_length_mismatch(self):
        packet = serialize_packet(1, 0, 1, b"hello world")
        # Truncate 3 bytes from payload
        truncated = packet[:-5] + packet[-2:]
        with self.assertRaises(ValueError):
            deserialize_packet(truncated)

        # Extra trailing garbage bytes
        with self.assertRaises(ValueError):
            deserialize_packet(packet + b"\x00\x00\x00")

    def test_checksum_corruption(self):
        packet = bytearray(serialize_packet(2, 1, 999, b"critical data"))

        # Corrupt payload byte
        packet_payload_corrupted = bytearray(packet)
        packet_payload_corrupted[12] ^= 0xFF
        with self.assertRaises(ValueError):
            deserialize_packet(bytes(packet_payload_corrupted))

        # Corrupt checksum byte itself
        packet_checksum_corrupted = bytearray(packet)
        packet_checksum_corrupted[-1] ^= 0x01
        with self.assertRaises(ValueError):
            deserialize_packet(bytes(packet_checksum_corrupted))


if __name__ == "__main__":
    unittest.main()
