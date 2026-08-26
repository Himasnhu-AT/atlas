"""
Generator pipelines and lazy stream processing.

Implement composable generator stages for batching (chunking), sliding windows,
lazy predicate filtering and transformation, and k-way sorted stream merging.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Iterator, Optional


def chunk_stream(stream: Iterable[Any], chunk_size: int) -> Iterator[list[Any]]:
    """
    Yield successive non-overlapping chunks of up to chunk_size items from a stream.

    If the stream terminates with fewer than chunk_size remaining items, yield the
    remaining items as a final partial chunk. If the stream is empty, yield nothing.

    Args:
        stream: An input iterable of elements.
        chunk_size: Maximum number of elements in each yielded chunk. Must be > 0.

    Returns:
        An iterator yielding lists of elements of length <= chunk_size.

    Raises:
        ValueError: If chunk_size <= 0.

    Examples:
        >>> list(chunk_stream([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    raise NotImplementedError


def sliding_window(
    stream: Iterable[Any],
    window_size: int,
    step: int = 1,
) -> Iterator[list[Any]]:
    """
    Yield rolling sliding windows of length window_size, advancing by step elements each time.

    Only full windows of length window_size are yielded. If the stream contains
    fewer than window_size elements, yield nothing.

    Args:
        stream: An input iterable of elements.
        window_size: Exact number of elements in each yielded window. Must be > 0.
        step: Number of elements to advance between successive windows. Must be > 0.

    Returns:
        An iterator yielding lists of length window_size.

    Raises:
        ValueError: If window_size <= 0 or step <= 0.

    Examples:
        >>> list(sliding_window([1, 2, 3, 4, 5], window_size=3, step=1))
        [[1, 2, 3], [2, 3, 4], [3, 4, 5]]
        >>> list(sliding_window([1, 2, 3, 4, 5], window_size=2, step=2))
        [[1, 2], [3, 4]]
    """
    raise NotImplementedError


def filter_transform_pipeline(
    stream: Iterable[Any],
    predicates: list[Callable[[Any], bool]],
    transform: Callable[[Any], Any],
) -> Iterator[Any]:
    """
    Filter stream items by multiple predicates and apply a transformation function lazily.

    For each item in stream, if all predicate functions return True, yield transform(item).

    Args:
        stream: An input iterable of elements.
        predicates: A list of functions taking an element and returning a bool.
        transform: A function transforming each passing element into an output value.

    Returns:
        An iterator yielding transformed elements that satisfied all predicates.

    Examples:
        >>> evens_squared = filter_transform_pipeline(
        ...     [1, 2, 3, 4, 5, 6],
        ...     predicates=[lambda x: x % 2 == 0, lambda x: x > 2],
        ...     transform=lambda x: x * x,
        ... )
        >>> list(evens_squared)
        [16, 36]
    """
    raise NotImplementedError


def merge_sorted_streams(
    *streams: Iterable[Any],
    key: Optional[Callable[[Any], Any]] = None,
) -> Iterator[Any]:
    """
    Merge multiple pre-sorted iterables into a single sorted iterator using a min-heap.

    Maintains at most one active element per input stream in memory, achieving
    O(K) space complexity where K is the number of streams.

    Args:
        *streams: Input iterables, each already sorted in ascending order.
        key: Optional unary key extraction function for comparisons.

    Returns:
        An iterator yielding elements in sorted order.

    Examples:
        >>> list(merge_sorted_streams([1, 4, 7], [2, 5, 8], [3, 6, 9]))
        [1, 2, 3, 4, 5, 6, 7, 8, 9]
    """
    raise NotImplementedError
