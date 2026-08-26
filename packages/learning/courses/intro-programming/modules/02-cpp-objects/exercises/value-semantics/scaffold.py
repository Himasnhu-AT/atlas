"""
Value semantics and immutable value objects.

Implement an immutable Money class representing an integer number of cents
and a 3-letter currency code.
"""

from __future__ import annotations
from typing import Any


class Money:
    """
    Immutable value object representing an amount of money in cents and currency.
    """

    def __init__(self, amount_cents: int, currency: str = "USD") -> None:
        """
        Initialize Money with an integer number of cents and a currency code.

        Args:
            amount_cents: Integer count of cents.
            currency: 3-letter uppercase alphabetic currency code (e.g. 'USD').

        Raises:
            TypeError: If amount_cents is not an int or currency is not a str.
            ValueError: If currency is not a 3-letter uppercase alphabetic string.
        """
        raise NotImplementedError

    @property
    def amount_cents(self) -> int:
        """Return the integer count of cents."""
        raise NotImplementedError

    @property
    def currency(self) -> str:
        """Return the 3-letter currency code."""
        raise NotImplementedError

    def add(self, other: Money) -> Money:
        """
        Add another Money instance to this one.

        Args:
            other: Money instance to add.

        Returns:
            A new Money instance with the summed cents.

        Raises:
            TypeError: If other is not a Money instance.
            ValueError: If currencies do not match.
        """
        raise NotImplementedError

    def subtract(self, other: Money) -> Money:
        """
        Subtract another Money instance from this one.

        Args:
            other: Money instance to subtract.

        Returns:
            A new Money instance with the subtracted cents.

        Raises:
            TypeError: If other is not a Money instance.
            ValueError: If currencies do not match.
        """
        raise NotImplementedError

    def multiply(self, factor: float) -> Money:
        """
        Multiply this Money instance by a factor, rounding to the nearest cent.

        Args:
            factor: Numeric multiplier (int or float).

        Returns:
            A new Money instance with rounded cents.

        Raises:
            TypeError: If factor is not an int or float.
        """
        raise NotImplementedError

    def equals(self, other: Any) -> bool:
        """
        Compare equality with another object.

        Returns:
            True if other is a Money instance with identical cents and currency, False otherwise.
        """
        raise NotImplementedError

    def to_string(self) -> str:
        """
        Format the monetary value as a string.

        Format:
            "$12.34 USD" for positive values.
            "-$12.34 USD" for negative values.
            "$0.00 USD" for zero.
        """
        raise NotImplementedError
