"""
Tests for: C3 linearization and method resolution order (MRO).

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import compute_c3_mro, resolve_attribute


class TestC3Linearization(unittest.TestCase):
    def test_single_inheritance(self):
        graph = {
            "O": [],
            "A": ["O"],
            "B": ["A"],
            "C": ["B"],
        }
        self.assertEqual(compute_c3_mro("O", graph), ["O"])
        self.assertEqual(compute_c3_mro("A", graph), ["A", "O"])
        self.assertEqual(compute_c3_mro("B", graph), ["B", "A", "O"])
        self.assertEqual(compute_c3_mro("C", graph), ["C", "B", "A", "O"])

    def test_diamond_inheritance(self):
        graph = {
            "O": [],
            "A": ["O"],
            "B": ["O"],
            "D": ["A", "B"],
        }
        self.assertEqual(compute_c3_mro("D", graph), ["D", "A", "B", "O"])

    def test_complex_hierarchy(self):
        # Classic C3 test case from Python documentation
        graph = {
            "O": [],
            "F": ["O"],
            "E": ["O"],
            "D": ["O"],
            "C": ["D", "F"],
            "B": ["E", "D"],
            "A": ["B", "C"],
        }
        self.assertEqual(compute_c3_mro("O", graph), ["O"])
        self.assertEqual(compute_c3_mro("D", graph), ["D", "O"])
        self.assertEqual(compute_c3_mro("E", graph), ["E", "O"])
        self.assertEqual(compute_c3_mro("F", graph), ["F", "O"])
        self.assertEqual(compute_c3_mro("B", graph), ["B", "E", "D", "O"])
        self.assertEqual(compute_c3_mro("C", graph), ["C", "D", "F", "O"])
        self.assertEqual(compute_c3_mro("A", graph), ["A", "B", "E", "C", "D", "F", "O"])

    def test_inconsistent_hierarchy_raises_type_error(self):
        # X requires A before B; Y requires B before A; Z tries to inherit from X and Y
        graph = {
            "O": [],
            "A": ["O"],
            "B": ["O"],
            "X": ["A", "B"],
            "Y": ["B", "A"],
            "Z": ["X", "Y"],
        }
        with self.assertRaises(TypeError):
            compute_c3_mro("Z", graph)

    def test_unlisted_isolated_class(self):
        graph = {}
        self.assertEqual(compute_c3_mro("Standalone", graph), ["Standalone"])


class TestAttributeResolution(unittest.TestCase):
    def setUp(self):
        self.class_attrs = {
            "O": {"name": "object_base", "root_id": 0},
            "A": {"name": "class_a", "a_val": 10},
            "B": {"name": "class_b", "b_val": 20},
            "D": {"d_val": 30},
        }
        self.mro_map = {
            "D": ["D", "A", "B", "O"],
        }

    def test_resolves_inherited_attribute_following_mro(self):
        # D does not define 'name', so it should resolve to A's 'name' before B's
        self.assertEqual(resolve_attribute("D", "name", self.class_attrs, self.mro_map), "class_a")
        self.assertEqual(resolve_attribute("D", "d_val", self.class_attrs, self.mro_map), 30)
        self.assertEqual(resolve_attribute("D", "a_val", self.class_attrs, self.mro_map), 10)
        self.assertEqual(resolve_attribute("D", "b_val", self.class_attrs, self.mro_map), 20)
        self.assertEqual(resolve_attribute("D", "root_id", self.class_attrs, self.mro_map), 0)

    def test_missing_attribute_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            resolve_attribute("D", "non_existent", self.class_attrs, self.mro_map)


if __name__ == "__main__":
    unittest.main(verbosity=2)
