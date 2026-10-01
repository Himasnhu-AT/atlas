from __future__ import annotations

from typing import Any


class StackVM:
    """
    A stack-based bytecode virtual machine supporting arithmetic,
    variable storage, comparisons, and control-flow jumps.
    """

    def __init__(self) -> None:
        """Initialize the virtual machine with empty stack, variable store, and PC."""
        self.stack: list[Any] = []
        self.variables: dict[str, Any] = {}
        self.pc: int = 0

    def run(self, instructions: list[tuple]) -> Any:
        """
        Execute a sequence of bytecode instructions until RETURN or program end.

        Returns the value popped by RETURN, or the top of the stack if instructions end.
        """
        self.stack.clear()
        self.variables.clear()
        self.pc = 0

        while 0 <= self.pc < len(instructions):
            inst = instructions[self.pc]
            op = inst[0]
            arg = inst[1] if len(inst) > 1 else None
            self.pc += 1

            if op == "LOAD_CONST":
                self.stack.append(arg)
            elif op == "LOAD_VAR":
                if arg not in self.variables:
                    raise KeyError(f"Variable '{arg}' is not defined")
                self.stack.append(self.variables[arg])
            elif op == "STORE_VAR":
                val = self.stack.pop()
                self.variables[arg] = val
            elif op == "ADD":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            elif op == "SUB":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)
            elif op == "MUL":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            elif op == "DIV":
                b = self.stack.pop()
                a = self.stack.pop()
                if b == 0:
                    raise ZeroDivisionError("Division by zero in StackVM")
                if isinstance(a, int) and isinstance(b, int):
                    self.stack.append(a // b)
                else:
                    self.stack.append(a / b)
            elif op == "CMP_EQ":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a == b)
            elif op == "CMP_LT":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a < b)
            elif op == "JUMP":
                self.pc = arg
            elif op == "JUMP_IF_FALSE":
                cond = self.stack.pop()
                if not cond:
                    self.pc = arg
            elif op == "POP":
                self.stack.pop()
            elif op == "RETURN":
                return self.stack.pop() if self.stack else None
            else:
                raise ValueError(f"Unknown opcode '{op}' at PC {self.pc - 1}")

        return self.stack.pop() if self.stack else None

    def get_variable(self, name: str) -> Any:
        """Retrieve the value of a variable from the local environment table."""
        if name not in self.variables:
            raise KeyError(f"Variable '{name}' is not defined")
        return self.variables[name]

    def get_stack(self) -> list[Any]:
        """Return a copy of the current operand stack."""
        return list(self.stack)
