"""
Closures, memoization, and retry decorators.

Implement stateful closures, a bounded LRU/FIFO memoization decorator with cache statistics,
and an exponential backoff retry decorator with metadata preservation.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable


def make_counter(start: int = 0, step: int = 1) -> Callable[[], int]:
    """
    Create an incremental counter closure.

    Args:
        start: The initial value returned on the first invocation.
        step: The amount to increment the counter after each invocation.

    Returns:
        A zero-argument callable that returns the current value and increments its internal state.

    Examples:
        >>> c = make_counter(start=10, step=2)
        >>> c()
        10
        >>> c()
        12
    """
    current = start

    def counter() -> int:
        nonlocal current
        val = current
        current += step
        return val

    return counter


def memoize(max_size: int = 128) -> Callable[[Callable], Any]:
    """
    Decorator factory that caches the return values of a function up to max_size entries.

    The decorated function must preserve its original metadata (__name__, __doc__, etc.)
    and attach two control methods:
      - .cache_info() -> dict[str, int]: returns {"hits": int, "misses": int, "size": int, "max_size": int}
      - .cache_clear() -> None: clears the cache and resets hit/miss counters to 0.

    When the cache exceeds max_size entries upon inserting a new entry, the oldest entry is evicted.

    Args:
        max_size: Maximum number of distinct call arguments to retain in cache.

    Returns:
        The decorator function.
    """
    def decorator(fn: Callable) -> Any:
        cache: dict[tuple, Any] = {}
        hits = 0
        misses = 0

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal hits, misses
            key = (args, tuple(sorted(kwargs.items())))
            if key in cache:
                hits += 1
                return cache[key]

            misses += 1
            result = fn(*args, **kwargs)
            if len(cache) >= max_size and key not in cache:
                first_key = next(iter(cache))
                del cache[first_key]
            cache[key] = result
            return result

        def cache_info() -> dict[str, int]:
            return {
                "hits": hits,
                "misses": misses,
                "size": len(cache),
                "max_size": max_size,
            }

        def cache_clear() -> None:
            nonlocal hits, misses
            cache.clear()
            hits = 0
            misses = 0

        wrapper.cache_info = cache_info  # type: ignore
        wrapper.cache_clear = cache_clear  # type: ignore
        return wrapper

    return decorator


def retry(max_attempts: int, backoff_factor: float = 1.0) -> Callable[[Callable], Any]:
    """
    Decorator factory that retries a failing function up to max_attempts times.

    If the decorated function raises an Exception, execution is retried up to max_attempts
    times. Between failed attempts, execution sleeps for backoff_factor * (2 ** (attempt - 1))
    seconds if backoff_factor > 0 (where attempt is 1 for the first failure).
    If all max_attempts fail, the final exception is re-raised.

    Args:
        max_attempts: Maximum number of execution attempts. Must be >= 1.
        backoff_factor: Multiplier for exponential backoff sleep delay.

    Returns:
        The decorator function.

    Raises:
        ValueError: If max_attempts < 1.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    def decorator(fn: Callable) -> Any:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as err:
                    last_exception = err
                    if attempt < max_attempts and backoff_factor > 0:
                        time.sleep(backoff_factor * (2 ** (attempt - 1)))
            if last_exception is not None:
                raise last_exception

        return wrapper

    return decorator
