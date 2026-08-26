"""
Call stack simulator.

Simulates execution activation records, frame pointers, local variable scope,
and call stack unwinding.

Run `python3 test.py` to test your implementation.
"""

from __future__ import annotations

from typing import Any


class Frame:
    """
    Activation record representing a single function call frame on the stack.
    """

    def __init__(
        self,
        function_name: str,
        args: dict[str, Any],
        return_address: int,
        locals: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize an activation frame.

        Args:
            function_name: Identifier of the function being executed.
            args: Dictionary of formal argument names and their bound values.
            return_address: Instruction pointer address to resume execution after return.
            locals: Dictionary of local variable bindings (defaults to empty dict).
        """
        raise NotImplementedError


class CallStack:
    """
    Fixed-capacity execution call stack managing nested activation frames.
    """

    def __init__(self, max_depth: int = 64) -> None:
        """
        Initialize a call stack with a maximum frame depth limit.

        Args:
            max_depth: Maximum number of active frames before stack overflow.

        Raises:
            ValueError: If max_depth is not positive.
        """
        raise NotImplementedError

    def push_frame(
        self,
        function_name: str,
        args: dict[str, Any],
        return_address: int,
    ) -> Frame:
        """
        Push a new activation frame onto the call stack.

        Args:
            function_name: Name of the invoked function.
            args: Key-value mapping of function parameters.
            return_address: Address to return to upon function exit.

        Returns:
            The newly created Frame instance.

        Raises:
            RecursionError: If pushing exceeds max_depth.
        """
        raise NotImplementedError

    def pop_frame(self) -> tuple[str, int]:
        """
        Pop the topmost activation frame from the call stack.

        Returns:
            A tuple of (function_name, return_address).

        Raises:
            IndexError: If the call stack is empty.
        """
        raise NotImplementedError

    def get_local(self, var_name: str) -> Any:
        """
        Look up a variable in the active (topmost) frame.

        Checks frame locals first, falling back to frame args.

        Args:
            var_name: Name of variable to look up.

        Returns:
            The value bound to var_name.

        Raises:
            IndexError: If the call stack is empty.
            KeyError: If var_name is not found in locals or args.
        """
        raise NotImplementedError

    def set_local(self, var_name: str, value: Any) -> None:
        """
        Set or overwrite a local variable in the active (topmost) frame.

        Args:
            var_name: Name of local variable.
            value: Value to bind.

        Raises:
            IndexError: If the call stack is empty.
        """
        raise NotImplementedError

    def current_depth(self) -> int:
        """Return the number of active frames currently on the stack."""
        raise NotImplementedError

    def unwind_trace(self) -> list[str]:
        """
        Return the stack trace as a list of function names from bottom to top.

        Returns:
            List of function names starting from root caller to current top frame.
        """
        raise NotImplementedError
