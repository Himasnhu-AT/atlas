from __future__ import annotations

import unittest
from solution import calculate_struct_layout, optimize_struct_layout


class TestStructPaddingCalculator(unittest.TestCase):
    def test_empty_fields(self):
        result = calculate_struct_layout([])
        self.assertEqual(result["total_size"], 0)
        self.assertEqual(result["alignment"], 1)
        self.assertEqual(result["field_offsets"], {})
        self.assertEqual(result["padding_bytes"], 0)

        optimized = optimize_struct_layout([])
        self.assertEqual(optimized, [])

    def test_single_field(self):
        result = calculate_struct_layout([("val", 4, 4)])
        self.assertEqual(result["total_size"], 4)
        self.assertEqual(result["alignment"], 4)
        self.assertEqual(result["field_offsets"], {"val": 0})
        self.assertEqual(result["padding_bytes"], 0)

    def test_single_byte_field(self):
        result = calculate_struct_layout([("b", 1, 1)])
        self.assertEqual(result["total_size"], 1)
        self.assertEqual(result["alignment"], 1)
        self.assertEqual(result["field_offsets"], {"b": 0})
        self.assertEqual(result["padding_bytes"], 0)

    def test_sensor_reading_unaligned(self):
        # char status (1, 1) -> offset 0
        # int reading (4, 4) -> pad 3, offset 4
        # char flag (1, 1) -> offset 8
        # int64_t timestamp (8, 8) -> pad 7, offset 16
        # final offset 24, max_align 8 -> total size 24
        # data bytes = 1 + 4 + 1 + 8 = 14, padding = 10
        fields = [
            ("status", 1, 1),
            ("reading", 4, 4),
            ("flag", 1, 1),
            ("timestamp", 8, 8),
        ]
        result = calculate_struct_layout(fields)
        self.assertEqual(result["total_size"], 24)
        self.assertEqual(result["alignment"], 8)
        self.assertEqual(
            result["field_offsets"],
            {"status": 0, "reading": 4, "flag": 8, "timestamp": 16},
        )
        self.assertEqual(result["padding_bytes"], 10)

    def test_trailing_padding(self):
        # int64_t timestamp (8, 8) -> offset 0
        # char flag (1, 1) -> offset 8
        # final offset 9 -> rounded to 16
        fields = [("timestamp", 8, 8), ("flag", 1, 1)]
        result = calculate_struct_layout(fields)
        self.assertEqual(result["total_size"], 16)
        self.assertEqual(result["alignment"], 8)
        self.assertEqual(result["field_offsets"], {"timestamp": 0, "flag": 8})
        self.assertEqual(result["padding_bytes"], 7)

    def test_already_aligned_struct(self):
        fields = [
            ("a", 8, 8),
            ("b", 4, 4),
            ("c", 2, 2),
            ("d", 1, 1),
            ("e", 1, 1),
        ]
        result = calculate_struct_layout(fields)
        self.assertEqual(result["total_size"], 16)
        self.assertEqual(result["alignment"], 8)
        self.assertEqual(
            result["field_offsets"],
            {"a": 0, "b": 8, "c": 12, "d": 14, "e": 15},
        )
        self.assertEqual(result["padding_bytes"], 0)

    def test_optimize_struct_layout(self):
        unoptimized = [
            ("status", 1, 1),
            ("reading", 4, 4),
            ("flag", 1, 1),
            ("timestamp", 8, 8),
        ]
        optimized = optimize_struct_layout(unoptimized)
        self.assertEqual(
            optimized,
            [
                ("timestamp", 8, 8),
                ("reading", 4, 4),
                ("status", 1, 1),
                ("flag", 1, 1),
            ],
        )

        opt_result = calculate_struct_layout(optimized)
        self.assertEqual(opt_result["total_size"], 16)
        self.assertEqual(opt_result["padding_bytes"], 2)
        self.assertEqual(
            opt_result["field_offsets"],
            {"timestamp": 0, "reading": 8, "status": 12, "flag": 13},
        )

    def test_optimize_stability(self):
        fields = [
            ("field_a", 2, 2),
            ("field_b", 2, 2),
            ("field_c", 4, 4),
            ("field_d", 2, 2),
        ]
        optimized = optimize_struct_layout(fields)
        self.assertEqual(
            optimized,
            [
                ("field_c", 4, 4),
                ("field_a", 2, 2),
                ("field_b", 2, 2),
                ("field_d", 2, 2),
            ],
        )


if __name__ == "__main__":
    unittest.main()
