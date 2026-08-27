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
        self.name = name
        self.parent = parent
        self.methods: dict[str, Callable] = {}

    def add_method(self, method_name: str, fn: Callable) -> None:
        """
        Register or override a method in this vtable.
        """
        self.methods[method_name] = fn

    def get_method(self, method_name: str) -> Callable:
        """
        Look up a method by name. Searches this vtable first, then traverses
        the parent inheritance hierarchy. Raises AttributeError if not found.
        """
        if method_name in self.methods:
            return self.methods[method_name]
        if self.parent is not None:
            return self.parent.get_method(method_name)
        raise AttributeError(
            f"Method '{method_name}' not found in class hierarchy of '{self.name}'"
        )


class ObjectInstance:
    """
    Object instance containing a vptr reference and an instance field dictionary.
    """

    def __init__(self, vtable: VTable, fields: dict[str, Any]) -> None:
        """
        Initialize an object instance with its vptr (vtable) and field dictionary.
        """
        self.vptr = vtable
        self.fields = dict(fields)

    def invoke(self, method_name: str, *args: Any) -> Any:
        """
        Dispatch a method invocation dynamically through the vptr.
        Passes self (the instance) as the first parameter to the resolved function.
        """
        fn = self.vptr.get_method(method_name)
        return fn(self, *args)


def define_class(
    name: str,
    parent: Optional[VTable] = None,
    methods: Optional[dict[str, Callable]] = None,
) -> VTable:
    """
    Construct a new VTable with the given name, parent class, and method dictionary.
    """
    vt = VTable(name, parent)
    if methods:
        for method_name, fn in methods.items():
            vt.add_method(method_name, fn)
    return vt


def instantiate(vtable: VTable, **fields: Any) -> ObjectInstance:
    """
    Instantiate a new ObjectInstance bound to the specified vtable with keyword fields.
    """
    return ObjectInstance(vtable, fields)
