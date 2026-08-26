from __future__ import annotations

from typing import Any, Callable, Optional


class VTable:
    """
    Virtual method table representation for class-level method dispatch.
    """

    def __init__(self, name: str, parent: Optional[VTable] = None) -> None:
        """
        Initialize a vtable with a class name and an optional parent vtable.
        """
        raise NotImplementedError

    def add_method(self, method_name: str, fn: Callable) -> None:
        """
        Register or override a method in this vtable.
        """
        raise NotImplementedError

    def get_method(self, method_name: str) -> Callable:
        """
        Look up a method by name. Searches this vtable first, then traverses
        the parent inheritance hierarchy. Raises AttributeError if not found.
        """
        raise NotImplementedError


class ObjectInstance:
    """
    Object instance containing a vptr reference and an instance field dictionary.
    """

    def __init__(self, vtable: VTable, fields: dict[str, Any]) -> None:
        """
        Initialize an object instance with its vptr (vtable) and field dictionary.
        """
        raise NotImplementedError

    def invoke(self, method_name: str, *args: Any) -> Any:
        """
        Dispatch a method invocation dynamically through the vptr.
        Passes self (the instance) as the first parameter to the resolved function.
        """
        raise NotImplementedError


def define_class(
    name: str,
    parent: Optional[VTable] = None,
    methods: Optional[dict[str, Callable]] = None,
) -> VTable:
    """
    Construct a new VTable with the given name, parent class, and method dictionary.
    """
    raise NotImplementedError


def instantiate(vtable: VTable, **fields: Any) -> ObjectInstance:
    """
    Instantiate a new ObjectInstance bound to the specified vtable with keyword fields.
    """
    raise NotImplementedError
