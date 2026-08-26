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
        raise NotImplementedError

    def unpack_return(self, raw_bytes: bytes, c_type: CType) -> Any:
        """
        Unmarshal raw C return bytes back into a high-level Python value.

        - INT32: Unpack 4-byte signed little-endian integer
        - FLOAT64: Unpack 8-byte double-precision little-endian float
        - CSTRING: Decode UTF-8 string with null terminator stripped
        """
        raise NotImplementedError

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
        raise NotImplementedError

    def call(self, name: str, *args: Any) -> Any:
        """
        Marshal Python arguments, invoke the registered foreign function,
        and unmarshal the returned raw bytes.
        """
        raise NotImplementedError
