"""
C3 linearization and method resolution order (MRO).

Implement the C3 linearization merge algorithm used by Python to compute
monotonic Method Resolution Order in multiple inheritance hierarchies, and
resolve dynamic attributes across class dictionaries.
"""

from __future__ import annotations

from typing import Any


def compute_c3_mro(
    class_name: str,
    inheritance_graph: dict[str, list[str]],
) -> list[str]:
    """
    Compute the C3 linearization Method Resolution Order (MRO) for a given class.

    Given a class name and an inheritance graph mapping each class to its list of direct base classes,
    compute L[C] = [C] + merge(L[B1], L[B2], ..., [B1, B2, ...]).

    Args:
        class_name: The target class name to linearize.
        inheritance_graph: A dictionary mapping class names to lists of immediate base class names.
            A class with no bases maps to an empty list or may be omitted from the dictionary.

    Returns:
        The linear list of class names in method resolution order starting with class_name.

    Raises:
        TypeError: If the inheritance hierarchy cannot be consistently linearized.

    Examples:
        >>> graph = {"O": [], "A": ["O"], "B": ["O"], "C": ["A", "B"]}
        >>> compute_c3_mro("C", graph)
        ['C', 'A', 'B', 'O']
    """
    raise NotImplementedError


def resolve_attribute(
    class_name: str,
    attr_name: str,
    class_attrs: dict[str, dict[str, Any]],
    mro_map: dict[str, list[str]],
) -> Any:
    """
    Resolve an attribute by searching class dictionaries according to the class's MRO.

    Args:
        class_name: The name of the class where attribute lookup begins.
        attr_name: The attribute name to resolve.
        class_attrs: A dictionary mapping class names to their class dictionary of attributes.
        mro_map: A dictionary mapping class names to their precomputed MRO lists.

    Returns:
        The value of the attribute found in the earliest class in the MRO.

    Raises:
        AttributeError: If attr_name is not defined in any class in the MRO.

    Examples:
        >>> attrs = {"A": {"val": 1}, "B": {"val": 2, "extra": "b"}, "O": {"val": 0}}
        >>> mros = {"C": ["C", "A", "B", "O"]}
        >>> resolve_attribute("C", "val", attrs, mros)
        1
        >>> resolve_attribute("C", "extra", attrs, mros)
        'b'
    """
    raise NotImplementedError
