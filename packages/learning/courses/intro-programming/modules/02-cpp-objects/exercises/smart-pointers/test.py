"""
Tests for smart-pointers exercise.

Run with `python3 test.py`.
"""

from __future__ import annotations
import unittest
from solution import ControlBlock, SharedPtr, WeakPtr


class TestSharedPtrBasics(unittest.TestCase):
    def test_single_owner_lifecycle(self):
        sp = SharedPtr("managed_resource")
        self.assertEqual(sp.use_count(), 1)
        self.assertEqual(sp.get(), "managed_resource")

        sp.reset()
        self.assertEqual(sp.use_count(), 0)
        with self.assertRaises(RuntimeError):
            sp.get()

    def test_multiple_owners_sharing(self):
        sp1 = SharedPtr({"key": "data"})
        sp2 = sp1.clone()
        sp3 = sp2.clone()

        self.assertEqual(sp1.use_count(), 3)
        self.assertEqual(sp2.use_count(), 3)
        self.assertEqual(sp3.use_count(), 3)
        self.assertIs(sp1.get(), sp2.get())

        sp1.reset()
        self.assertEqual(sp1.use_count(), 0)
        self.assertEqual(sp2.use_count(), 2)
        self.assertEqual(sp3.use_count(), 2)

        sp2.reset()
        self.assertEqual(sp3.use_count(), 1)
        self.assertEqual(sp3.get(), {"key": "data"})

        sp3.reset()
        self.assertEqual(sp3.use_count(), 0)

    def test_clears_value_on_zero_use_count(self):
        cb = ControlBlock(value="secret_data")
        sp = SharedPtr(control_block=cb)
        self.assertEqual(cb.value, "secret_data")

        sp.reset()
        self.assertIsNone(cb.value, "ControlBlock.value must be set to None when use_count drops to 0")

    def test_null_pointer_operations(self):
        sp = SharedPtr()
        self.assertEqual(sp.use_count(), 0)
        with self.assertRaises(RuntimeError):
            sp.get()
        with self.assertRaises(RuntimeError):
            sp.clone()
        with self.assertRaises(RuntimeError):
            sp.to_weak()
        # Resetting null pointer should not error
        sp.reset()


class TestWeakPtrBasics(unittest.TestCase):
    def test_weak_observer_does_not_affect_use_count(self):
        sp = SharedPtr("observed_data")
        self.assertEqual(sp.use_count(), 1)

        wp = sp.to_weak()
        self.assertEqual(sp.use_count(), 1, "Creating a weak_ptr must not increment use_count")
        self.assertEqual(wp.use_count(), 1)
        self.assertFalse(wp.expired())

    def test_lock_acquires_shared_ownership(self):
        sp = SharedPtr("lockable_payload")
        wp = sp.to_weak()

        locked = wp.lock()
        self.assertIsNotNone(locked)
        assert locked is not None
        self.assertEqual(locked.get(), "lockable_payload")
        self.assertEqual(sp.use_count(), 2)
        self.assertEqual(locked.use_count(), 2)

        locked.reset()
        self.assertEqual(sp.use_count(), 1)

    def test_weak_ptr_expires_when_shared_pointers_reset(self):
        sp = SharedPtr("transient_object")
        wp = sp.to_weak()

        self.assertFalse(wp.expired())
        sp.reset()

        self.assertTrue(wp.expired())
        self.assertEqual(wp.use_count(), 0)
        self.assertIsNone(wp.lock(), "lock() on expired WeakPtr must return None")

    def test_default_unattached_weak_ptr(self):
        wp = WeakPtr()
        self.assertTrue(wp.expired())
        self.assertEqual(wp.use_count(), 0)
        self.assertIsNone(wp.lock())


if __name__ == "__main__":
    unittest.main(verbosity=2)
