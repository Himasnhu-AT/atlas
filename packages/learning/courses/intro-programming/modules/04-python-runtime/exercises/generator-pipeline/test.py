"""
Tests for: Generator pipelines and lazy stream processing.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    chunk_stream,
    filter_transform_pipeline,
    merge_sorted_streams,
    sliding_window,
)


class TestChunkStream(unittest.TestCase):
    def test_even_chunks(self):
        result = list(chunk_stream([1, 2, 3, 4], 2))
        self.assertEqual(result, [[1, 2], [3, 4]])

    def test_partial_final_chunk(self):
        result = list(chunk_stream([1, 2, 3, 4, 5], 2))
        self.assertEqual(result, [[1, 2], [3, 4], [5]])

    def test_empty_stream(self):
        result = list(chunk_stream([], 3))
        self.assertEqual(result, [])

    def test_single_element_chunk_size(self):
        result = list(chunk_stream([1, 2, 3], 1))
        self.assertEqual(result, [[1], [2], [3]])

    def test_invalid_chunk_size_raises_value_error(self):
        with self.assertRaises(ValueError):
            list(chunk_stream([1, 2], 0))
        with self.assertRaises(ValueError):
            list(chunk_stream([1, 2], -2))


class TestSlidingWindow(unittest.TestCase):
    def test_step_one(self):
        result = list(sliding_window([1, 2, 3, 4, 5], window_size=3, step=1))
        self.assertEqual(result, [[1, 2, 3], [2, 3, 4], [3, 4, 5]])

    def test_step_two(self):
        result = list(sliding_window([1, 2, 3, 4, 5, 6], window_size=3, step=2))
        self.assertEqual(result, [[1, 2, 3], [3, 4, 5]])

    def test_step_greater_than_window_size(self):
        result = list(sliding_window([1, 2, 3, 4, 5, 6, 7], window_size=2, step=3))
        self.assertEqual(result, [[1, 2], [4, 5]])

    def test_stream_shorter_than_window(self):
        result = list(sliding_window([1, 2], window_size=3, step=1))
        self.assertEqual(result, [])

    def test_invalid_parameters_raises_value_error(self):
        with self.assertRaises(ValueError):
            list(sliding_window([1, 2], window_size=0, step=1))
        with self.assertRaises(ValueError):
            list(sliding_window([1, 2], window_size=2, step=0))


class TestFilterTransformPipeline(unittest.TestCase):
    def test_filtering_and_transforming(self):
        numbers = range(1, 11)
        predicates = [lambda x: x % 2 == 0, lambda x: x > 4]
        transform = lambda x: x * 10

        result = list(filter_transform_pipeline(numbers, predicates, transform))
        # Even and > 4: 6, 8, 10 -> * 10: 60, 80, 100
        self.assertEqual(result, [60, 80, 100])

    def test_empty_predicates_transforms_all(self):
        result = list(filter_transform_pipeline([1, 2, 3], [], lambda x: x + 1))
        self.assertEqual(result, [2, 3, 4])

    def test_no_matches(self):
        result = list(filter_transform_pipeline([1, 3, 5], [lambda x: x % 2 == 0], lambda x: x))
        self.assertEqual(result, [])


class TestMergeSortedStreams(unittest.TestCase):
    def test_merges_multiple_sorted_streams(self):
        s1 = [1, 4, 7, 10]
        s2 = [2, 5, 8]
        s3 = [3, 6, 9, 11, 12]
        result = list(merge_sorted_streams(s1, s2, s3))
        self.assertEqual(result, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

    def test_handles_empty_streams(self):
        s1 = [1, 3, 5]
        s2 = []
        s3 = [2, 4]
        result = list(merge_sorted_streams(s1, s2, s3))
        self.assertEqual(result, [1, 2, 3, 4, 5])

    def test_all_empty_streams(self):
        result = list(merge_sorted_streams([], [], []))
        self.assertEqual(result, [])

    def test_custom_key_function(self):
        # Sort by absolute distance from 10
        s1 = [10, 12, 15]  # diffs: 0, 2, 5
        s2 = [9, 7, 3]     # diffs: 1, 3, 7
        key_fn = lambda x: abs(x - 10)
        result = list(merge_sorted_streams(s1, s2, key=key_fn))
        self.assertEqual(result, [10, 9, 12, 7, 15, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
