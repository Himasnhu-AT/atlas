"""
Tests for call stack simulator.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest

from solution import (
    CallStack,
    Frame,
)


class TestFrame(unittest.TestCase):
    def test_frame_initialization(self):
        f = Frame("compute", {"x": 10, "y": 20}, 0x401050)
        self.assertEqual(f.function_name, "compute")
        self.assertEqual(f.args, {"x": 10, "y": 20})
        self.assertEqual(f.return_address, 0x401050)
        self.assertEqual(f.locals, {})

    def test_frame_custom_locals(self):
        f = Frame("main", {}, 0x0, locals={"status": 0})
        self.assertEqual(f.locals, {"status": 0})


class TestCallStack(unittest.TestCase):
    def test_push_and_depth(self):
        stack = CallStack(max_depth=4)
        self.assertEqual(stack.current_depth(), 0)

        f1 = stack.push_frame("main", {}, 0x0)
        self.assertEqual(stack.current_depth(), 1)
        self.assertEqual(f1.function_name, "main")

        f2 = stack.push_frame("parse_header", {"fd": 3}, 0x400100)
        self.assertEqual(stack.current_depth(), 2)
        self.assertEqual(f2.args["fd"], 3)

    def test_pop_frame(self):
        stack = CallStack()
        stack.push_frame("main", {}, 0x0)
        stack.push_frame("worker", {"task_id": 42}, 0x400250)

        name, ret = stack.pop_frame()
        self.assertEqual(name, "worker")
        self.assertEqual(ret, 0x400250)
        self.assertEqual(stack.current_depth(), 1)

        name, ret = stack.pop_frame()
        self.assertEqual(name, "main")
        self.assertEqual(ret, 0x0)
        self.assertEqual(stack.current_depth(), 0)

    def test_pop_empty_raises(self):
        stack = CallStack()
        with self.assertRaises(IndexError):
            stack.pop_frame()

    def test_stack_overflow_limit(self):
        stack = CallStack(max_depth=3)
        stack.push_frame("f1", {}, 0x1)
        stack.push_frame("f2", {}, 0x2)
        stack.push_frame("f3", {}, 0x3)
        with self.assertRaises(RecursionError):
            stack.push_frame("f4", {}, 0x4)

    def test_invalid_max_depth(self):
        with self.assertRaises(ValueError):
            CallStack(max_depth=0)
        with self.assertRaises(ValueError):
            CallStack(max_depth=-5)

    def test_variable_lookup_and_mutation(self):
        stack = CallStack()
        stack.push_frame("calculate", {"base": 100, "rate": 5}, 0x401000)

        # Lookup from args
        self.assertEqual(stack.get_local("base"), 100)
        self.assertEqual(stack.get_local("rate"), 5)

        # Set and get local
        stack.set_local("temp_result", 500)
        self.assertEqual(stack.get_local("temp_result"), 500)

        # Local shadows argument with same name
        stack.set_local("base", 200)
        self.assertEqual(stack.get_local("base"), 200)

    def test_variable_lookup_isolation(self):
        stack = CallStack()
        stack.push_frame("caller", {"data": "parent_data"}, 0x0)
        stack.set_local("var_a", 111)

        stack.push_frame("callee", {"param": 999}, 0x400500)
        stack.set_local("var_b", 222)

        # Callee scope cannot see caller locals or args
        self.assertEqual(stack.get_local("param"), 999)
        self.assertEqual(stack.get_local("var_b"), 222)
        with self.assertRaises(KeyError):
            stack.get_local("data")
        with self.assertRaises(KeyError):
            stack.get_local("var_a")

        # After pop, caller scope is restored
        stack.pop_frame()
        self.assertEqual(stack.get_local("data"), "parent_data")
        self.assertEqual(stack.get_local("var_a"), 111)

    def test_empty_stack_variable_access_raises(self):
        stack = CallStack()
        with self.assertRaises(IndexError):
            stack.get_local("x")
        with self.assertRaises(IndexError):
            stack.set_local("x", 10)

    def test_unwind_trace(self):
        stack = CallStack()
        self.assertEqual(stack.unwind_trace(), [])

        stack.push_frame("main", {}, 0x0)
        stack.push_frame("dispatch", {}, 0x10)
        stack.push_frame("handle_request", {}, 0x20)
        stack.push_frame("read_body", {}, 0x30)

        self.assertEqual(
            stack.unwind_trace(),
            ["main", "dispatch", "handle_request", "read_body"],
        )

        stack.pop_frame()
        self.assertEqual(
            stack.unwind_trace(),
            ["main", "dispatch", "handle_request"],
        )


if __name__ == '__main__':
    unittest.main()
