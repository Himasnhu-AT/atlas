"""
Call stack simulator: reference solution.
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
        self.function_name = function_name
        self.args = dict(args)
        self.return_address = return_address
        self.locals = dict(locals) if locals is not None else {}


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
        if max_depth <= 0:
            raise ValueError("max_depth must be positive")
        self.max_depth = max_depth
        self._frames: list[Frame] = []

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
        if len(self._frames) >= self.max_depth:
            raise RecursionError(f"Stack overflow: maximum depth {self.max_depth} reached")
        frame = Frame(function_name=function_name, args=args, return_address=return_address)
        self._frames.append(frame)
        return frame

    def pop_frame(self) -> tuple[str, int]:
        """
        Pop the topmost activation frame from the call stack.

        Returns:
            A tuple of (function_name, return_address).

        Raises:
            IndexError: If the call stack is empty.
        """
        if not self._frames:
            raise IndexError("Cannot pop from empty call stack")
        frame = self._frames.pop()
        return (frame.function_name, frame.return_address)

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
        if not self._frames:
            raise IndexError("Call stack is empty")
        top = self._frames[-1]
        if var_name in top.locals:
            return top.locals[var_name]
        if var_name in top.args:
            return top.args[var_name]
        raise KeyError(f"Variable '{var_name}' not found in active frame '{top.function_name}'")

    def set_local(self, var_name: str, value: Any) -> None:
        """
        Set or overwrite a local variable in the active (topmost) frame.

        Args:
            var_name: Name of local variable.
            value: Value to bind.

        Raises:
            IndexError: If the call stack is empty.
        """
        if not self._frames:
            raise IndexError("Call stack is empty")
        self._frames[-1].locals[var_name] = value

    def current_depth(self) -> int:
        """Return the number of active frames currently on the stack."""
        return len(self._frames)

    def unwind_trace(self) -> list[str]:
        """
        Return the stack trace as a list of function names from bottom to top.

        Returns:
            List of function names starting from root caller to current top frame.
        """
        return [f.function_name for f in self._frames]
