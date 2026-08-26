import math
import struct
import unittest
from solution import CType, FFIBridge


class TestFFIBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = FFIBridge()

    def test_pack_unpack_int32(self) -> None:
        raw = self.bridge.pack_argument(42, CType.INT32)
        self.assertEqual(len(raw), 4)
        self.assertEqual(raw, struct.pack("<i", 42))
        self.assertEqual(self.bridge.unpack_return(raw, CType.INT32), 42)

        neg_raw = self.bridge.pack_argument(-100, CType.INT32)
        self.assertEqual(self.bridge.unpack_return(neg_raw, CType.INT32), -100)

    def test_pack_unpack_float64(self) -> None:
        val = 3.141592653589793
        raw = self.bridge.pack_argument(val, CType.FLOAT64)
        self.assertEqual(len(raw), 8)
        self.assertEqual(raw, struct.pack("<d", val))
        self.assertAlmostEqual(self.bridge.unpack_return(raw, CType.FLOAT64), val, places=10)

    def test_pack_unpack_cstring(self) -> None:
        text = "Hello, Atlas!"
        raw = self.bridge.pack_argument(text, CType.CSTRING)
        self.assertEqual(raw, b"Hello, Atlas!\x00")
        self.assertEqual(self.bridge.unpack_return(raw, CType.CSTRING), text)

    def test_foreign_addition(self) -> None:
        # C callable simulating: int32_t add(int32_t a, int32_t b)
        def c_add(args: list[bytes]) -> bytes:
            a = struct.unpack("<i", args[0])[0]
            b = struct.unpack("<i", args[1])[0]
            return struct.pack("<i", a + b)

        self.bridge.register_function("c_add", [CType.INT32, CType.INT32], CType.INT32, c_add)
        result = self.bridge.call("c_add", 15, 27)
        self.assertEqual(result, 42)

    def test_foreign_hypot(self) -> None:
        # C callable simulating: double hypot(double x, double y)
        def c_hypot(args: list[bytes]) -> bytes:
            x = struct.unpack("<d", args[0])[0]
            y = struct.unpack("<d", args[1])[0]
            return struct.pack("<d", math.sqrt(x * x + y * y))

        self.bridge.register_function("c_hypot", [CType.FLOAT64, CType.FLOAT64], CType.FLOAT64, c_hypot)
        result = self.bridge.call("c_hypot", 3.0, 4.0)
        self.assertAlmostEqual(result, 5.0, places=7)

    def test_foreign_string_transform(self) -> None:
        # C callable simulating: char* to_upper(const char* s)
        def c_to_upper(args: list[bytes]) -> bytes:
            s = args[0].rstrip(b"\x00").decode("utf-8")
            upper_s = s.upper()
            return upper_s.encode("utf-8") + b"\x00"

        self.bridge.register_function("c_to_upper", [CType.CSTRING], CType.CSTRING, c_to_upper)
        result = self.bridge.call("c_to_upper", "virtual machine")
        self.assertEqual(result, "VIRTUAL MACHINE")

    def test_multi_type_signature(self) -> None:
        # C callable: char* format_entry(int32_t id, double score, const char* name)
        def c_format_entry(args: list[bytes]) -> bytes:
            item_id = struct.unpack("<i", args[0])[0]
            score = struct.unpack("<d", args[1])[0]
            name = args[2].rstrip(b"\x00").decode("utf-8")
            res = f"[{item_id}] {name}: {score:.2f}"
            return res.encode("utf-8") + b"\x00"

        self.bridge.register_function(
            "format_entry",
            [CType.INT32, CType.FLOAT64, CType.CSTRING],
            CType.CSTRING,
            c_format_entry,
        )
        result = self.bridge.call("format_entry", 7, 98.65, "Atlas VM")
        self.assertEqual(result, "[7] Atlas VM: 98.65")

    def test_unregistered_function_error(self) -> None:
        with self.assertRaises(KeyError):
            self.bridge.call("non_existent_func", 1, 2)

    def test_argument_count_mismatch(self) -> None:
        def dummy_fn(args: list[bytes]) -> bytes:
            return struct.pack("<i", 0)

        self.bridge.register_function("dummy", [CType.INT32, CType.INT32], CType.INT32, dummy_fn)
        with self.assertRaises(TypeError):
            self.bridge.call("dummy", 10)  # Provided 1 arg instead of 2


if __name__ == "__main__":
    unittest.main()
