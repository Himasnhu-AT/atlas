"""
RAII resource management and scope guards.

Implement ScopeExit for LIFO cleanup execution and TransactionGuard for
context-managed commit/rollback transactions.
"""

from __future__ import annotations
from typing import Callable, Optional, Any


class ScopeExit:
    """
    Scope exit manager executing registered cleanup callbacks in strict LIFO order.
    """

    def __init__(self) -> None:
        """Initialize an empty ScopeExit guard."""
        self._actions: list[Callable[[], None]] = []

    def register(self, action: Callable[[], None]) -> None:
        """
        Register a cleanup callback to be executed upon scope exit.

        Args:
            action: Zero-argument callable.

        Raises:
            TypeError: If action is not callable.
        """
        if not callable(action):
            raise TypeError("action must be callable")
        self._actions.append(action)

    def execute(self) -> None:
        """
        Execute all registered callbacks in reverse order of registration (LIFO).
        Clears the callback list so actions are executed at most once.
        """
        while self._actions:
            cb = self._actions.pop()
            cb()

    def dismiss(self) -> None:
        """
        Dismiss all registered callbacks without executing them.
        """
        self._actions.clear()


class TransactionGuard:
    """
    RAII transaction manager that commits on normal exit and rolls back on exception.
    """

    def __init__(
        self,
        on_commit: Optional[Callable[[], None]] = None,
        on_rollback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize a TransactionGuard.

        Args:
            on_commit: Optional callback invoked when the transaction commits.
            on_rollback: Optional callback invoked when the transaction rolls back.
        """
        self._on_commit = on_commit
        self._on_rollback = on_rollback
        self._completed = False

    def commit(self) -> None:
        """
        Commit the transaction, invoking the on_commit callback if registered.

        Raises:
            RuntimeError: If the transaction has already been committed or rolled back.
        """
        if self._completed:
            raise RuntimeError("Transaction already completed")
        self._completed = True
        if self._on_commit is not None:
            self._on_commit()

    def rollback(self) -> None:
        """
        Roll back the transaction, invoking the on_rollback callback if registered.

        Raises:
            RuntimeError: If the transaction has already been committed or rolled back.
        """
        if self._completed:
            raise RuntimeError("Transaction already completed")
        self._completed = True
        if self._on_rollback is not None:
            self._on_rollback()

    def __enter__(self) -> TransactionGuard:
        """Enter the runtime context and return the TransactionGuard."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """
        Exit the runtime context. Calls rollback if an exception occurred, commit otherwise.
        Always returns False so exceptions propagate.
        """
        if exc_type is not None:
            if not self._completed:
                self.rollback()
        else:
            if not self._completed:
                self.commit()
        return False
