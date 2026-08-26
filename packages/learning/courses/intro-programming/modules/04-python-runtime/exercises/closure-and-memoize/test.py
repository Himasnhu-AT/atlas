"""
Tests for: Closures, memoization, and retry decorators.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from solution import make_counter, memoize, retry


class TestMakeCounter(unittest.TestCase):
    def test_default_counter(self):
        c = make_counter()
        self.assertEqual(c(), 0)
        self.assertEqual(c(), 1)
        self.assertEqual(c(), 2)

    def test_custom_start_and_step(self):
        c = make_counter(start=100, step=5)
        self.assertEqual(c(), 100)
        self.assertEqual(c(), 105)
        self.assertEqual(c(), 110)

    def test_negative_step(self):
        c = make_counter(start=10, step=-3)
        self.assertEqual(c(), 10)
        self.assertEqual(c(), 7)
        self.assertEqual(c(), 4)

    def test_independent_closure_instances(self):
        c1 = make_counter(start=0, step=1)
        c2 = make_counter(start=100, step=10)
        self.assertEqual(c1(), 0)
        self.assertEqual(c2(), 100)
        self.assertEqual(c1(), 1)
        self.assertEqual(c2(), 110)


class TestMemoize(unittest.TestCase):
    def test_caches_calls_and_tracks_info(self):
        call_count = 0

        @memoize(max_size=10)
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            nonlocal call_count
            call_count += 1
            return a + b

        self.assertEqual(add.__name__, "add")
        self.assertEqual(add.__doc__, "Add two numbers.")

        self.assertEqual(add(2, 3), 5)
        self.assertEqual(call_count, 1)
        self.assertEqual(add.cache_info(), {"hits": 0, "misses": 1, "size": 1, "max_size": 10})

        # Second identical call should hit cache
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(call_count, 1)
        self.assertEqual(add.cache_info(), {"hits": 1, "misses": 1, "size": 1, "max_size": 10})

        # Keyword arguments
        self.assertEqual(add(a=2, b=3), 5)
        self.assertEqual(call_count, 2)
        self.assertEqual(add.cache_info(), {"hits": 1, "misses": 2, "size": 2, "max_size": 10})

        self.assertEqual(add(a=2, b=3), 5)
        self.assertEqual(call_count, 2)
        self.assertEqual(add.cache_info(), {"hits": 2, "misses": 2, "size": 2, "max_size": 10})

    def test_eviction_when_max_size_exceeded(self):
        @memoize(max_size=2)
        def square(x: int) -> int:
            return x * x

        square(1)  # cache: {1: 1}
        square(2)  # cache: {1: 1, 2: 4}
        self.assertEqual(square.cache_info()["size"], 2)

        square(3)  # cache: {2: 4, 3: 9} (1 evicted)
        self.assertEqual(square.cache_info()["size"], 2)

        # 1 was evicted, so this is a miss
        initial_misses = square.cache_info()["misses"]
        square(1)
        self.assertEqual(square.cache_info()["misses"], initial_misses + 1)

    def test_cache_clear(self):
        @memoize(max_size=5)
        def compute(n: int) -> int:
            return n * 10

        compute(1)
        compute(1)
        self.assertEqual(compute.cache_info()["hits"], 1)
        self.assertEqual(compute.cache_info()["size"], 1)

        compute.cache_clear()
        self.assertEqual(compute.cache_info(), {"hits": 0, "misses": 0, "size": 0, "max_size": 5})


class TestRetry(unittest.TestCase):
    def test_succeeds_on_first_try(self):
        attempts = 0

        @retry(max_attempts=3, backoff_factor=0.0)
        def successful():
            nonlocal attempts
            attempts += 1
            return "ok"

        self.assertEqual(successful(), "ok")
        self.assertEqual(attempts, 1)

    def test_succeeds_after_retries(self):
        attempts = 0

        @retry(max_attempts=3, backoff_factor=0.0)
        def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError(f"Fail attempt {attempts}")
            return "recovered"

        self.assertEqual(flaky(), "recovered")
        self.assertEqual(attempts, 3)

    def test_fails_exhausted_retries_raises_last_exception(self):
        attempts = 0

        @retry(max_attempts=3, backoff_factor=0.0)
        def broken():
            nonlocal attempts
            attempts += 1
            raise ValueError(f"Permanent error {attempts}")

        with self.assertRaises(ValueError) as ctx:
            broken()
        self.assertEqual(attempts, 3)
        self.assertEqual(str(ctx.exception), "Permanent error 3")

    def test_invalid_max_attempts_raises_value_error(self):
        with self.assertRaises(ValueError):
            retry(max_attempts=0)

    @patch("time.sleep")
    def test_exponential_backoff_sleep_called(self, mock_sleep):
        attempts = 0

        @retry(max_attempts=3, backoff_factor=1.5)
        def failing():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise KeyError("retry needed")
            return "done"

        self.assertEqual(failing(), "done")
        self.assertEqual(mock_sleep.call_count, 2)
        # Attempt 1 failed -> delay = 1.5 * (2**0) = 1.5
        # Attempt 2 failed -> delay = 1.5 * (2**1) = 3.0
        mock_sleep.assert_any_call(1.5)
        mock_sleep.assert_any_call(3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
