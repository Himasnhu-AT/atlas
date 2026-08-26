from __future__ import annotations

import unittest
from solution import DynamicArray


class TestDynamicArray(unittest.TestCase):
    def test_initial_state(self):
        arr = DynamicArray(initial_capacity=4)
        self.assertEqual(arr.size(), 0)
        self.assertEqual(arr.capacity(), 4)

        arr_default = DynamicArray()
        self.assertEqual(arr_default.size(), 0)
        self.assertEqual(arr_default.capacity(), 4)

    def test_push_back_and_get(self):
        arr = DynamicArray(initial_capacity=2)
        arr.push_back(10)
        arr.push_back(20)
        self.assertEqual(arr.size(), 2)
        self.assertEqual(arr.capacity(), 2)
        self.assertEqual(arr.get(0), 10)
        self.assertEqual(arr.get(1), 20)

        # Trigger doubling
        arr.push_back(30)
        self.assertEqual(arr.size(), 3)
        self.assertEqual(arr.capacity(), 4)
        self.assertEqual(arr.get(2), 30)

        arr.push_back(40)
        arr.push_back(50)
        self.assertEqual(arr.size(), 5)
        self.assertEqual(arr.capacity(), 8)

    def test_pop_back(self):
        arr = DynamicArray(initial_capacity=4)
        with self.assertRaises(IndexError):
            arr.pop_back()

        arr.push_back(100)
        arr.push_back(200)
        self.assertEqual(arr.pop_back(), 200)
        self.assertEqual(arr.size(), 1)
        self.assertEqual(arr.pop_back(), 100)
        self.assertEqual(arr.size(), 0)

        with self.assertRaises(IndexError):
            arr.pop_back()

    def test_get_set_bounds(self):
        arr = DynamicArray(initial_capacity=4)
        arr.push_back("a")
        arr.push_back("b")

        self.assertEqual(arr.get(0), "a")
        arr.set(0, "z")
        self.assertEqual(arr.get(0), "z")

        with self.assertRaises(IndexError):
            arr.get(-1)
        with self.assertRaises(IndexError):
            arr.get(2)
        with self.assertRaises(IndexError):
            arr.get(5)
        with self.assertRaises(IndexError):
            arr.set(-1, "x")
        with self.assertRaises(IndexError):
            arr.set(2, "x")

    def test_insert_middle_and_shift(self):
        arr = DynamicArray(initial_capacity=2)
        arr.push_back(10)
        arr.push_back(30)

        # Insert at index 1 -> [10, 20, 30] (triggers doubling to 4)
        arr.insert(1, 20)
        self.assertEqual(arr.size(), 3)
        self.assertEqual(arr.capacity(), 4)
        self.assertEqual(arr.get(0), 10)
        self.assertEqual(arr.get(1), 20)
        self.assertEqual(arr.get(2), 30)

        # Insert at head (index 0)
        arr.insert(0, 5)
        self.assertEqual(arr.size(), 4)
        self.assertEqual(arr.get(0), 5)
        self.assertEqual(arr.get(1), 10)

        # Insert at tail (index == size)
        arr.insert(4, 40)
        self.assertEqual(arr.size(), 5)
        self.assertEqual(arr.capacity(), 8)
        self.assertEqual(arr.get(4), 40)

        with self.assertRaises(IndexError):
            arr.insert(-1, 0)
        with self.assertRaises(IndexError):
            arr.insert(10, 0)

    def test_remove_at(self):
        arr = DynamicArray(initial_capacity=4)
        arr.push_back(10)
        arr.push_back(20)
        arr.push_back(30)
        arr.push_back(40)

        # Remove middle element
        val = arr.remove_at(1)
        self.assertEqual(val, 20)
        self.assertEqual(arr.size(), 3)
        self.assertEqual(arr.get(0), 10)
        self.assertEqual(arr.get(1), 30)
        self.assertEqual(arr.get(2), 40)

        # Remove head
        val = arr.remove_at(0)
        self.assertEqual(val, 10)
        self.assertEqual(arr.size(), 2)
        self.assertEqual(arr.get(0), 30)

        # Remove tail
        val = arr.remove_at(1)
        self.assertEqual(val, 40)
        self.assertEqual(arr.size(), 1)
        self.assertEqual(arr.get(0), 30)

        with self.assertRaises(IndexError):
            arr.remove_at(1)
        with self.assertRaises(IndexError):
            arr.remove_at(-1)

    def test_shrink_to_fit(self):
        arr = DynamicArray(initial_capacity=16)
        for i in range(5):
            arr.push_back(i)
        self.assertEqual(arr.size(), 5)
        self.assertEqual(arr.capacity(), 16)

        arr.shrink_to_fit()
        self.assertEqual(arr.size(), 5)
        self.assertEqual(arr.capacity(), 5)
        for i in range(5):
            self.assertEqual(arr.get(i), i)

        empty_arr = DynamicArray(initial_capacity=8)
        empty_arr.shrink_to_fit()
        self.assertEqual(empty_arr.size(), 0)
        self.assertEqual(empty_arr.capacity(), 1)


if __name__ == "__main__":
    unittest.main()
