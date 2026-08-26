"""
Tests for raii-resource-guard exercise.

Run with `python3 test.py`.
"""

from __future__ import annotations
import unittest
from solution import ScopeExit, TransactionGuard


class TestScopeExit(unittest.TestCase):
    def test_lifo_execution_order(self):
        log = []
        scope = ScopeExit()
        scope.register(lambda: log.append("first"))
        scope.register(lambda: log.append("second"))
        scope.register(lambda: log.append("third"))

        scope.execute()
        self.assertEqual(log, ["third", "second", "first"])

    def test_dismiss_prevents_execution(self):
        log = []
        scope = ScopeExit()
        scope.register(lambda: log.append("action"))
        scope.dismiss()
        scope.execute()
        self.assertEqual(log, [])

    def test_execute_clears_callbacks(self):
        log = []
        scope = ScopeExit()
        scope.register(lambda: log.append("run"))
        scope.execute()
        self.assertEqual(log, ["run"])
        # Second execute should do nothing
        scope.execute()
        self.assertEqual(log, ["run"])

    def test_type_error_on_non_callable(self):
        scope = ScopeExit()
        with self.assertRaises(TypeError):
            scope.register("not a callable")  # type: ignore


class TestTransactionGuard(unittest.TestCase):
    def test_normal_completion_commits(self):
        committed = False
        rolled_back = False

        def on_commit():
            nonlocal committed
            committed = True

        def on_rollback():
            nonlocal rolled_back
            rolled_back = True

        with TransactionGuard(on_commit=on_commit, on_rollback=on_rollback) as guard:
            x = 10 + 20
            self.assertEqual(x, 30)

        self.assertTrue(committed)
        self.assertFalse(rolled_back)

    def test_exception_triggers_rollback_and_propagates(self):
        committed = False
        rolled_back = False

        def on_commit():
            nonlocal committed
            committed = True

        def on_rollback():
            nonlocal rolled_back
            rolled_back = True

        with self.assertRaises(ZeroDivisionError):
            with TransactionGuard(on_commit=on_commit, on_rollback=on_rollback):
                _ = 1 / 0

        self.assertFalse(committed)
        self.assertTrue(rolled_back)

    def test_manual_commit_inside_block(self):
        events = []
        with TransactionGuard(
            on_commit=lambda: events.append("commit"),
            on_rollback=lambda: events.append("rollback"),
        ) as guard:
            events.append("work")
            guard.commit()

        self.assertEqual(events, ["work", "commit"])

    def test_manual_rollback_inside_block(self):
        events = []
        with TransactionGuard(
            on_commit=lambda: events.append("commit"),
            on_rollback=lambda: events.append("rollback"),
        ) as guard:
            events.append("work")
            guard.rollback()

        self.assertEqual(events, ["work", "rollback"])

    def test_double_commit_raises_runtime_error(self):
        guard = TransactionGuard()
        guard.commit()
        with self.assertRaises(RuntimeError):
            guard.commit()

    def test_double_rollback_raises_runtime_error(self):
        guard = TransactionGuard()
        guard.rollback()
        with self.assertRaises(RuntimeError):
            guard.rollback()

    def test_commit_after_rollback_raises(self):
        guard = TransactionGuard()
        guard.rollback()
        with self.assertRaises(RuntimeError):
            guard.commit()

    def test_none_callbacks_supported(self):
        # Should not raise any errors when callbacks are None
        with TransactionGuard() as guard:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
