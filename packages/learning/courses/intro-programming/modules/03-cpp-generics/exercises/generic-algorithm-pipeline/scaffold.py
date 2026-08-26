from __future__ import annotations

from typing import Any, Callable, Iterable, Optional


def transform(iterable: Iterable[Any], fn: Callable[[Any], Any]) -> list[Any]:
    """
    Apply a callable to each element in an iterable and return the transformed elements in a list.
    """
    raise NotImplementedError


def filter_if(iterable: Iterable[Any], predicate: Callable[[Any], bool]) -> list[Any]:
    """
    Filter elements from an iterable, returning only elements where predicate(item) evaluates to True.
    """
    raise NotImplementedError


def accumulate(
    iterable: Iterable[Any], init: Any, binary_op: Callable[[Any, Any], Any]
) -> Any:
    """
    Fold elements sequentially using a binary operator, starting from an initial value.
    """
    raise NotImplementedError


def partition(
    iterable: Iterable[Any], predicate: Callable[[Any], bool]
) -> tuple[list[Any], list[Any]]:
    """
    Partition elements into two lists: (matching, non_matching) based on the predicate.
    Preserves relative element order.
    """
    raise NotImplementedError


def binary_search(
    sorted_list: list[Any],
    target: Any,
    key_fn: Optional[Callable[[Any], Any]] = None,
) -> int:
    """
    Perform binary search on a sorted list to find the index of target.
    If key_fn is provided, compares key_fn(item) against target.
    Returns the 0-based index of the matching element, or -1 if not found.
    """
    raise NotImplementedError
