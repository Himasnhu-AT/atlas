from __future__ import annotations

import unittest
from solution import OpenAddressingHashMap


class TestOpenAddressingHashMap(unittest.TestCase):
    def test_initial_state(self):
        hmap = OpenAddressingHashMap(initial_capacity=8, max_load_factor=0.66)
        self.assertEqual(hmap.size(), 0)
        self.assertEqual(hmap.capacity(), 8)
        self.assertEqual(hmap.load_factor(), 0.0)
        self.assertFalse(hmap.contains("key"))

    def test_put_get_contains_single(self):
        hmap = OpenAddressingHashMap(initial_capacity=8)
        hmap.put("name", "Atlas")
        self.assertEqual(hmap.size(), 1)
        self.assertTrue(hmap.contains("name"))
        self.assertEqual(hmap.get("name"), "Atlas")
        self.assertAlmostEqual(hmap.load_factor(), 1 / 8)

    def test_update_existing_key(self):
        hmap = OpenAddressingHashMap(initial_capacity=8)
        hmap.put("score", 100)
        self.assertEqual(hmap.get("score"), 100)
        self.assertEqual(hmap.size(), 1)

        hmap.put("score", 200)
        self.assertEqual(hmap.get("score"), 200)
        self.assertEqual(hmap.size(), 1)
        self.assertEqual(hmap.capacity(), 8)

    def test_missing_key_raises_key_error(self):
        hmap = OpenAddressingHashMap()
        with self.assertRaises(KeyError):
            hmap.get("missing")
        with self.assertRaises(KeyError):
            hmap.remove("missing")

    def test_linear_probing_and_collision_retrieval(self):
        hmap = OpenAddressingHashMap(initial_capacity=16, max_load_factor=0.9)
        # Insert multiple keys
        keys = [f"item_{i}" for i in range(10)]
        for i, k in enumerate(keys):
            hmap.put(k, i * 10)

        self.assertEqual(hmap.size(), 10)
        for i, k in enumerate(keys):
            self.assertTrue(hmap.contains(k))
            self.assertEqual(hmap.get(k), i * 10)

    def test_tombstone_preserves_probe_chain(self):
        # We use a small capacity to force probing over collisions
        hmap = OpenAddressingHashMap(initial_capacity=8, max_load_factor=0.9)
        hmap.put("k1", "val1")
        hmap.put("k2", "val2")
        hmap.put("k3", "val3")
        hmap.put("k4", "val4")

        # Remove an element in the middle
        hmap.remove("k2")
        self.assertFalse(hmap.contains("k2"))
        self.assertEqual(hmap.size(), 3)

        with self.assertRaises(KeyError):
            hmap.get("k2")

        # Elements after k2 in the table must still be found
        self.assertTrue(hmap.contains("k1"))
        self.assertTrue(hmap.contains("k3"))
        self.assertTrue(hmap.contains("k4"))
        self.assertEqual(hmap.get("k3"), "val3")
        self.assertEqual(hmap.get("k4"), "val4")

    def test_tombstone_recycling(self):
        hmap = OpenAddressingHashMap(initial_capacity=8, max_load_factor=0.9)
        hmap.put("a", 1)
        hmap.put("b", 2)
        hmap.remove("a")
        self.assertEqual(hmap.size(), 1)

        # Insert new key which should recycle slot
        hmap.put("c", 3)
        self.assertEqual(hmap.size(), 2)
        self.assertEqual(hmap.get("c"), 3)
        self.assertEqual(hmap.get("b"), 2)

    def test_dynamic_rehashing_and_capacity_growth(self):
        # Initial capacity 4, threshold 0.66 -> threshold is >= 2.64, so 3 items trigger rehash
        hmap = OpenAddressingHashMap(initial_capacity=4, max_load_factor=0.66)
        self.assertEqual(hmap.capacity(), 4)

        hmap.put("x1", 10)
        hmap.put("x2", 20)
        self.assertEqual(hmap.capacity(), 4)

        # Third element triggers rehashing
        hmap.put("x3", 30)
        self.assertGreaterEqual(hmap.capacity(), 8)
        self.assertEqual(hmap.size(), 3)
        self.assertEqual(hmap.get("x1"), 10)
        self.assertEqual(hmap.get("x2"), 20)
        self.assertEqual(hmap.get("x3"), 30)

        # Insert many more elements to force further resizes
        for i in range(4, 30):
            hmap.put(f"key_{i}", i)

        self.assertEqual(hmap.size(), 29)
        for i in range(4, 30):
            self.assertEqual(hmap.get(f"key_{i}"), i)


if __name__ == "__main__":
    unittest.main()
