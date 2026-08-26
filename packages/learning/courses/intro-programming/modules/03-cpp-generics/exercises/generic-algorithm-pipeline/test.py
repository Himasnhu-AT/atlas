from __future__ import annotations

import unittest
from solution import accumulate, binary_search, filter_if, partition, transform


class TestGenericAlgorithmPipeline(unittest.TestCase):
    def test_transform_empty_and_types(self):
        self.assertEqual(transform([], lambda x: x * 2), [])
        self.assertEqual(transform([1, 2, 3, 4], lambda x: x * x), [1, 4, 9, 16])
        self.assertEqual(transform(["alpha", "beta"], str.upper), ["ALPHA", "BETA"])

        # Test with generator
        gen = (x for x in range(3))
        self.assertEqual(transform(gen, lambda x: x + 10), [10, 11, 12])

    def test_filter_if_scenarios(self):
        self.assertEqual(filter_if([], lambda x: True), [])
        self.assertEqual(filter_if([1, 2, 3, 4, 5, 6], lambda x: x % 2 == 0), [2, 4, 6])
        self.assertEqual(
            filter_if(["cpp", "python", "c", "rust"], lambda s: len(s) > 3),
            ["python", "rust"],
        )

    def test_accumulate_operations(self):
        # Empty returns init
        self.assertEqual(accumulate([], 100, lambda acc, x: acc + x), 100)

        # Summation
        self.assertEqual(accumulate([1, 2, 3, 4, 5], 0, lambda acc, x: acc + x), 15)

        # Multiplication
        self.assertEqual(accumulate([2, 3, 4], 1, lambda acc, x: acc * x), 24)

        # String reduction
        self.assertEqual(
            accumulate(["b", "c", "d"], "a", lambda acc, s: f"{acc}->{s}"),
            "a->b->c->d",
        )

        # Dict reduction
        entries = [("k1", 10), ("k2", 20), ("k3", 30)]
        merged = accumulate(entries, {}, lambda d, item: {**d, item[0]: item[1]})
        self.assertEqual(merged, {"k1": 10, "k2": 20, "k3": 30})

    def test_partition_mechanics(self):
        self.assertEqual(partition([], lambda x: True), ([], []))

        # All pass
        self.assertEqual(
            partition([2, 4, 6], lambda x: x % 2 == 0),
            ([2, 4, 6], []),
        )

        # None pass
        self.assertEqual(
            partition([1, 3, 5], lambda x: x % 2 == 0),
            ([], [1, 3, 5]),
        )

        # Mixed preserving relative order
        items = [1, 2, 3, 4, 5, 6, 7, 8]
        evens, odds = partition(items, lambda x: x % 2 == 0)
        self.assertEqual(evens, [2, 4, 6, 8])
        self.assertEqual(odds, [1, 3, 5, 7])

    def test_binary_search_standard_cases(self):
        self.assertEqual(binary_search([], 5), -1)
        self.assertEqual(binary_search([10], 10), 0)
        self.assertEqual(binary_search([10], 5), -1)
        self.assertEqual(binary_search([10], 15), -1)

        arr = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
        # Search first, last, middle
        self.assertEqual(binary_search(arr, 2), 0)
        self.assertEqual(binary_search(arr, 91), 9)
        self.assertEqual(binary_search(arr, 16), 4)
        self.assertEqual(binary_search(arr, 23), 5)

        # Not found below, above, and between
        self.assertEqual(binary_search(arr, 1), -1)
        self.assertEqual(binary_search(arr, 100), -1)
        self.assertEqual(binary_search(arr, 15), -1)

    def test_binary_search_with_key_fn(self):
        records = [
            {"id": 101, "name": "Alice"},
            {"id": 204, "name": "Bob"},
            {"id": 305, "name": "Charlie"},
            {"id": 409, "name": "Diana"},
        ]

        idx = binary_search(records, 305, key_fn=lambda r: r["id"])
        self.assertEqual(idx, 2)
        self.assertEqual(records[idx]["name"], "Charlie")

        missing_idx = binary_search(records, 999, key_fn=lambda r: r["id"])
        self.assertEqual(missing_idx, -1)


if __name__ == "__main__":
    unittest.main()
