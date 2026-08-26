"""
Boxed object model and CPython PyObject simulation.

Implement a software model of CPython's PyObject header, reference counting,
small integer caching, value boxing, and identity vs equality checks.
"""

from __future__ import annotations

from typing import Any

_id_counter: int = 1


def _next_id() -> int:
    global _id_counter
    current = _id_counter
    _id_counter += 1
    return current


class PyObject:
    """
    A simulated CPython heap-allocated PyObject structure.

    Each object has a type name, an encapsulated value payload, a reference count
    initialized to 1, and a unique integer object ID representing its memory address.
    """

    def __init__(self, type_name: str, value: Any, object_id: int) -> None:
        """
        Initialize the PyObject with type_name, value, and object_id.
        ref_count must start at 1.
        """
        self.type_name: str = type_name
        self.value: Any = value
        self.ref_count: int = 1
        self.object_id: int = object_id

    def incref(self) -> None:
        """Increment the reference count of this object by 1."""
        self.ref_count += 1

    def decref(self) -> int:
        """
        Decrement the reference count of this object by 1.

        Returns the updated reference count.
        """
        self.ref_count -= 1
        return self.ref_count


_SMALL_INT_CACHE: dict[int, PyObject] = {
    i: PyObject("int", i, _next_id()) for i in range(-5, 257)
}


def box_int(val: int) -> PyObject:
    """
    Box an integer into a PyObject.

    Integers in the range [-5, 256] (inclusive) must be cached as singletons:
    repeated calls to box_int with the same value in this range must return the
    exact same PyObject instance. Integers outside this range must allocate a
    fresh PyObject with a new unique object_id on each call.
    """
    if -5 <= val <= 256:
        return _SMALL_INT_CACHE[val]
    return PyObject("int", val, _next_id())


def box_str(val: str) -> PyObject:
    """
    Box a string into a fresh PyObject with a new unique object_id.
    """
    return PyObject("str", val, _next_id())


def is_same(obj1: PyObject, obj2: PyObject) -> bool:
    """
    Determine if two PyObject instances represent the same object identity (pointer equality).

    Returns True if and only if both objects have the exact same object_id.
    """
    return obj1.object_id == obj2.object_id


def equals(obj1: PyObject, obj2: PyObject) -> bool:
    """
    Determine if two PyObject instances have equal values.

    Returns True if both objects have identical type_name and equal value.
    """
    return obj1.type_name == obj2.type_name and obj1.value == obj2.value
