from __future__ import annotations

from enum import Enum
import struct
from typing import Any, Callable, List


class CType(str, Enum):
    """Supported C Application Binary Interface (ABI) data types."""
    INT32 = "int32"
    FLOAT64 = "float64"
    CSTRING = "cstring"


class FFIBridge:
    """
    Foreign Function Interface (FFI) bridge for marshaling types and invoking
    native-like C ABI callables.
    """

    def __init__(self) -> None:
        """Initialize the FFI function registry."""
        self.functions: dict[str, dict[str, Any]] = {}

    def pack_argument(self, val: Any, c_type: CType) -> bytes:
        """
        Marshal a high-level Python value into a raw byte representation.

        - INT32: 4-byte signed integer, little-endian ('<i')
        - FLOAT64: 8-byte double-precision float, little-endian ('<d')
        - CSTRING: UTF-8 encoded bytes terminated by a null byte (b'\\x00')
        """
        if c_type == CType.INT32:
            return struct.pack("<i", int(val))
        elif c_type == CType.FLOAT64:
            return struct.pack("<d", float(val))
        elif c_type == CType.CSTRING:
            return str(val).encode("utf-8") + b"\x00"
        else:
            raise ValueError(f"Unsupported CType: {c_type}")

    def unpack_return(self, raw_bytes: bytes, c_type: CType) -> Any:
        """
        Unmarshal raw C return bytes back into a high-level Python value.

        - INT32: Unpack 4-byte signed little-endian integer
        - FLOAT64: Unpack 8-byte double-precision little-endian float
        - CSTRING: Decode UTF-8 string with null terminator stripped
        """
        if c_type == CType.INT32:
            return struct.unpack("<i", raw_bytes[:4])[0]
        elif c_type == CType.FLOAT64:
            return struct.unpack("<d", raw_bytes[:8])[0]
        elif c_type == CType.CSTRING:
            return raw_bytes.rstrip(b"\x00").decode("utf-8")
        else:
            raise ValueError(f"Unsupported CType: {c_type}")

    def register_function(
        self,
        name: str,
        arg_types: list[CType],
        return_type: CType,
        c_callable: Callable[[list[bytes]], bytes],
    ) -> None:
        """
        Register a foreign function signature and its underlying C-compatible callable.
        """
        self.functions[name] = {
            "arg_types": list(arg_types),
            "return_type": return_type,
            "c_callable": c_callable,
        }

    def call(self, name: str, *args: Any) -> Any:
        """
        Marshal Python arguments, invoke the registered foreign function,
        and unmarshal the returned raw bytes.
        """
        if name not in self.functions:
            raise KeyError(f"Foreign function '{name}' is not registered")

        fn = self.functions[name]
        arg_types: list[CType] = fn["arg_types"]

        if len(args) != len(arg_types):
            raise TypeError(
                f"Function '{name}' expects {len(arg_types)} arguments, got {len(args)}"
            )

        packed_args = [
            self.pack_argument(arg, c_type)
            for arg, c_type in zip(args, arg_types)
        ]

        raw_result = fn["c_callable"](packed_args)
        return self.unpack_return(raw_result, fn["return_type"])
