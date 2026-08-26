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
        raise NotImplementedError

    def get_variable(self, name: str) -> Any:
        """Retrieve the value of a variable from the local environment table."""
        raise NotImplementedError

    def get_stack(self) -> list[Any]:
        """Return a copy of the current operand stack."""
        raise NotImplementedError
