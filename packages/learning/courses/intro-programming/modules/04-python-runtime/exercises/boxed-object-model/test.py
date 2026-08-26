"""
Tests for: Boxed object model and CPython PyObject simulation.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import PyObject, box_int, box_str, equals, is_same


class TestPyObject(unittest.TestCase):
    def test_initial_state(self):
        obj = PyObject("int", 10, 1001)
        self.assertEqual(obj.type_name, "int")
        self.assertEqual(obj.value, 10)
        self.assertEqual(obj.object_id, 1001)
        self.assertEqual(obj.ref_count, 1)

    def test_incref_and_decref(self):
        obj = PyObject("str", "test", 1002)
        self.assertEqual(obj.ref_count, 1)

        obj.incref()
        self.assertEqual(obj.ref_count, 2)

        obj.incref()
        self.assertEqual(obj.ref_count, 3)

        new_count = obj.decref()
        self.assertEqual(new_count, 2)
        self.assertEqual(obj.ref_count, 2)

        new_count = obj.decref()
        self.assertEqual(new_count, 1)

        new_count = obj.decref()
        self.assertEqual(new_count, 0)


class TestSmallIntegerCache(unittest.TestCase):
    def test_cached_integers_share_identity(self):
        for val in [-5, -1, 0, 1, 42, 100, 256]:
            a = box_int(val)
            b = box_int(val)
            self.assertTrue(
                is_same(a, b),
                f"Integer {val} in [-5, 256] must share a single cached PyObject singleton.",
            )
            self.assertEqual(a.object_id, b.object_id)
            self.assertIs(a, b)

    def test_uncached_integers_get_fresh_allocations(self):
        for val in [-1000, -6, 257, 1000]:
            a = box_int(val)
            b = box_int(val)
            self.assertFalse(
                is_same(a, b),
                f"Integer {val} outside [-5, 256] must allocate a fresh PyObject on each call.",
            )
            self.assertNotEqual(a.object_id, b.object_id)
            self.assertIsNot(a, b)


class TestBoxingAndEquality(unittest.TestCase):
    def test_box_str_allocates_fresh_objects(self):
        s1 = box_str("hello")
        s2 = box_str("hello")
        self.assertEqual(s1.type_name, "str")
        self.assertEqual(s1.value, "hello")
        self.assertFalse(is_same(s1, s2))
        self.assertNotEqual(s1.object_id, s2.object_id)
        self.assertTrue(equals(s1, s2))

    def test_equality_matching_types_and_values(self):
        a = box_int(500)
        b = box_int(500)
        self.assertFalse(is_same(a, b))
        self.assertTrue(equals(a, b))

    def test_equality_different_values(self):
        a = box_int(10)
        b = box_int(20)
        self.assertFalse(equals(a, b))

    def test_equality_different_types(self):
        num = box_int(42)
        text = box_str("42")
        self.assertFalse(equals(num, text))
        self.assertFalse(is_same(num, text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
