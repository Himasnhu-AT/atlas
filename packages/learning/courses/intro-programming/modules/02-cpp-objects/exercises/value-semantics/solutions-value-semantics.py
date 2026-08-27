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
        if type(amount_cents) is not int:
            raise TypeError("amount_cents must be an integer")
        if not isinstance(currency, str):
            raise TypeError("currency must be a string")
        if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
            raise ValueError("currency must be a 3-letter uppercase alphabetic string")

        self._amount_cents = amount_cents
        self._currency = currency

    @property
    def amount_cents(self) -> int:
        """Return the integer count of cents."""
        return self._amount_cents

    @property
    def currency(self) -> str:
        """Return the 3-letter currency code."""
        return self._currency

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
        if not isinstance(other, Money):
            raise TypeError("other must be an instance of Money")
        if self._currency != other._currency:
            raise ValueError(f"Currency mismatch: {self._currency} and {other._currency}")
        return Money(self._amount_cents + other._amount_cents, self._currency)

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
        if not isinstance(other, Money):
            raise TypeError("other must be an instance of Money")
        if self._currency != other._currency:
            raise ValueError(f"Currency mismatch: {self._currency} and {other._currency}")
        return Money(self._amount_cents - other._amount_cents, self._currency)

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
        if isinstance(factor, bool) or not isinstance(factor, (int, float)):
            raise TypeError("factor must be an int or float")
        new_cents = round(self._amount_cents * factor)
        return Money(new_cents, self._currency)

    def equals(self, other: Any) -> bool:
        """
        Compare equality with another object.

        Returns:
            True if other is a Money instance with identical cents and currency, False otherwise.
        """
        if not isinstance(other, Money):
            return False
        return self._amount_cents == other._amount_cents and self._currency == other._currency

    def __eq__(self, other: Any) -> bool:
        return self.equals(other)

    def to_string(self) -> str:
        """
        Format the monetary value as a string.

        Format:
            "$12.34 USD" for positive values.
            "-$12.34 USD" for negative values.
            "$0.00 USD" for zero.
        """
        cents_abs = abs(self._amount_cents)
        dollars = cents_abs // 100
        cents = cents_abs % 100
        prefix = "-" if self._amount_cents < 0 else ""
        return f"{prefix}${dollars}.{cents:02d} {self._currency}"
