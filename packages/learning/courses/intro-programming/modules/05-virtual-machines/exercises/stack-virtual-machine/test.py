import unittest
from solution import StackVM


class TestStackVM(unittest.TestCase):
    def setUp(self) -> None:
        self.vm = StackVM()

    def test_basic_arithmetic(self) -> None:
        program = [
            ("LOAD_CONST", 10),
            ("LOAD_CONST", 20),
            ("ADD",),
            ("RETURN",),
        ]
        result = self.vm.run(program)
        self.assertEqual(result, 30)
        self.assertEqual(self.vm.get_stack(), [])

    def test_sub_mul_div(self) -> None:
        # (100 - 30) * 4 / 8 == 35
        program = [
            ("LOAD_CONST", 100),
            ("LOAD_CONST", 30),
            ("SUB",),
            ("LOAD_CONST", 4),
            ("MUL",),
            ("LOAD_CONST", 8),
            ("DIV",),
            ("RETURN",),
        ]
        result = self.vm.run(program)
        self.assertEqual(result, 35)

    def test_division_by_zero(self) -> None:
        program = [
            ("LOAD_CONST", 10),
            ("LOAD_CONST", 0),
            ("DIV",),
            ("RETURN",),
        ]
        with self.assertRaises(ZeroDivisionError):
            self.vm.run(program)

    def test_variables(self) -> None:
        program = [
            ("LOAD_CONST", 42),
            ("STORE_VAR", "x"),
            ("LOAD_CONST", 8),
            ("STORE_VAR", "y"),
            ("LOAD_VAR", "x"),
            ("LOAD_VAR", "y"),
            ("ADD",),
            ("STORE_VAR", "result"),
            ("LOAD_VAR", "result"),
            ("RETURN",),
        ]
        res = self.vm.run(program)
        self.assertEqual(res, 50)
        self.assertEqual(self.vm.get_variable("x"), 42)
        self.assertEqual(self.vm.get_variable("y"), 8)
        self.assertEqual(self.vm.get_variable("result"), 50)

        with self.assertRaises(KeyError):
            self.vm.get_variable("unknown_var")

    def test_comparison_eq_and_lt(self) -> None:
        prog_eq = [
            ("LOAD_CONST", 7),
            ("LOAD_CONST", 7),
            ("CMP_EQ",),
            ("RETURN",),
        ]
        self.assertTrue(self.vm.run(prog_eq))

        prog_lt = [
            ("LOAD_CONST", 10),
            ("LOAD_CONST", 5),
            ("CMP_LT",),
            ("RETURN",),
        ]
        self.assertFalse(self.vm.run(prog_lt))

        prog_lt_true = [
            ("LOAD_CONST", 5),
            ("LOAD_CONST", 10),
            ("CMP_LT",),
            ("RETURN",),
        ]
        self.assertTrue(self.vm.run(prog_lt_true))

    def test_jump_unconditional(self) -> None:
        program = [
            ("LOAD_CONST", 1),
            ("JUMP", 4),
            ("LOAD_CONST", 999),  # skipped
            ("ADD",),             # skipped
            ("LOAD_CONST", 2),
            ("ADD",),
            ("RETURN",),
        ]
        result = self.vm.run(program)
        self.assertEqual(result, 3)

    def test_jump_if_false(self) -> None:
        # if x < 10: result = 100 else: result = 200
        # When x = 5 (true branch)
        prog_true_branch = [
            ("LOAD_CONST", 5),
            ("STORE_VAR", "x"),
            ("LOAD_VAR", "x"),
            ("LOAD_CONST", 10),
            ("CMP_LT",),
            ("JUMP_IF_FALSE", 9),
            ("LOAD_CONST", 100),
            ("STORE_VAR", "res"),
            ("JUMP", 11),
            ("LOAD_CONST", 200),
            ("STORE_VAR", "res"),
            ("LOAD_VAR", "res"),
            ("RETURN",),
        ]
        self.assertEqual(self.vm.run(prog_true_branch), 100)

        # When x = 15 (false branch)
        prog_false_branch = [
            ("LOAD_CONST", 15),
            ("STORE_VAR", "x"),
            ("LOAD_VAR", "x"),
            ("LOAD_CONST", 10),
            ("CMP_LT",),
            ("JUMP_IF_FALSE", 9),
            ("LOAD_CONST", 100),
            ("STORE_VAR", "res"),
            ("JUMP", 11),
            ("LOAD_CONST", 200),
            ("STORE_VAR", "res"),
            ("LOAD_VAR", "res"),
            ("RETURN",),
        ]
        self.assertEqual(self.vm.run(prog_false_branch), 200)

    def test_loop_summation(self) -> None:
        # total = 0; i = 1; while i < 5: total += i; i += 1
        program = [
            # 0: total = 0
            ("LOAD_CONST", 0),
            # 1:
            ("STORE_VAR", "total"),
            # 2: i = 1
            ("LOAD_CONST", 1),
            # 3:
            ("STORE_VAR", "i"),
            # 4: Loop condition: i < 5
            ("LOAD_VAR", "i"),
            # 5:
            ("LOAD_CONST", 5),
            # 6:
            ("CMP_LT",),
            # 7: if not (i < 5), jump to return at 17
            ("JUMP_IF_FALSE", 17),
            # 8: total = total + i
            ("LOAD_VAR", "total"),
            # 9:
            ("LOAD_VAR", "i"),
            # 10:
            ("ADD",),
            # 11:
            ("STORE_VAR", "total"),
            # 12: i = i + 1
            ("LOAD_VAR", "i"),
            # 13:
            ("LOAD_CONST", 1),
            # 14:
            ("ADD",),
            # 15:
            ("STORE_VAR", "i"),
            # 16: Jump back to loop header
            ("JUMP", 4),
            # 17: RETURN total
            ("LOAD_VAR", "total"),
            # 18:
            ("RETURN",),
        ]
        result = self.vm.run(program)
        self.assertEqual(result, 10)
        self.assertEqual(self.vm.get_variable("total"), 10)
        self.assertEqual(self.vm.get_variable("i"), 5)

    def test_pop_instruction(self) -> None:
        program = [
            ("LOAD_CONST", 1),
            ("LOAD_CONST", 2),
            ("POP",),
            ("RETURN",),
        ]
        result = self.vm.run(program)
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
