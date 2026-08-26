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
        raise NotImplementedError

    def register(self, action: Callable[[], None]) -> None:
        """
        Register a cleanup callback to be executed upon scope exit.

        Args:
            action: Zero-argument callable.

        Raises:
            TypeError: If action is not callable.
        """
        raise NotImplementedError

    def execute(self) -> None:
        """
        Execute all registered callbacks in reverse order of registration (LIFO).
        Clears the callback list so actions are executed at most once.
        """
        raise NotImplementedError

    def dismiss(self) -> None:
        """
        Dismiss all registered callbacks without executing them.
        """
        raise NotImplementedError


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
        raise NotImplementedError

    def commit(self) -> None:
        """
        Commit the transaction, invoking the on_commit callback if registered.

        Raises:
            RuntimeError: If the transaction has already been committed or rolled back.
        """
        raise NotImplementedError

    def rollback(self) -> None:
        """
        Roll back the transaction, invoking the on_rollback callback if registered.

        Raises:
            RuntimeError: If the transaction has already been committed or rolled back.
        """
        raise NotImplementedError

    def __enter__(self) -> TransactionGuard:
        """Enter the runtime context and return the TransactionGuard."""
        raise NotImplementedError

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
        raise NotImplementedError
