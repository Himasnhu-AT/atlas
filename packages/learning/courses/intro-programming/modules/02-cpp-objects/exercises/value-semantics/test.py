"""
Tests for value-semantics exercise.

Run with `python3 test.py`.
"""

from __future__ import annotations
import unittest
from solution import Money


class TestMoneyValidation(unittest.TestCase):
    def test_valid_initialization(self):
        m = Money(1500, "USD")
        self.assertEqual(m.amount_cents, 1500)
        self.assertEqual(m.currency, "USD")

    def test_default_currency(self):
        m = Money(250)
        self.assertEqual(m.amount_cents, 250)
        self.assertEqual(m.currency, "USD")

    def test_invalid_cents_type(self):
        with self.assertRaises(TypeError):
            Money(12.34, "USD")  # type: ignore
        with self.assertRaises(TypeError):
            Money("100", "USD")  # type: ignore
        with self.assertRaises(TypeError):
            Money(True, "USD")  # type: ignore

    def test_invalid_currency(self):
        with self.assertRaises(ValueError):
            Money(100, "usd")  # lowercase
        with self.assertRaises(ValueError):
            Money(100, "US")  # too short
        with self.assertRaises(ValueError):
            Money(100, "USDT")  # too long
        with self.assertRaises(ValueError):
            Money(100, "U1D")  # non-alpha
        with self.assertRaises(TypeError):
            Money(100, 123)  # type: ignore


class TestMoneyImmutability(unittest.TestCase):
    def test_properties_are_read_only(self):
        m = Money(500, "USD")
        with self.assertRaises(AttributeError):
            m.amount_cents = 600  # type: ignore
        with self.assertRaises(AttributeError):
            m.currency = "EUR"  # type: ignore


class TestMoneyOperations(unittest.TestCase):
    def test_addition(self):
        m1 = Money(1050, "USD")
        m2 = Money(450, "USD")
        res = m1.add(m2)
        self.assertEqual(res.amount_cents, 1500)
        self.assertEqual(res.currency, "USD")
        # Ensure originals remain unchanged
        self.assertEqual(m1.amount_cents, 1050)
        self.assertEqual(m2.amount_cents, 450)

    def test_addition_currency_mismatch(self):
        m1 = Money(100, "USD")
        m2 = Money(100, "EUR")
        with self.assertRaises(ValueError):
            m1.add(m2)

    def test_addition_type_error(self):
        m = Money(100, "USD")
        with self.assertRaises(TypeError):
            m.add(100)  # type: ignore

    def test_subtraction(self):
        m1 = Money(1000, "USD")
        m2 = Money(300, "USD")
        res = m1.subtract(m2)
        self.assertEqual(res.amount_cents, 700)
        self.assertEqual(res.currency, "USD")

    def test_subtraction_negative_result(self):
        m1 = Money(300, "USD")
        m2 = Money(500, "USD")
        res = m1.subtract(m2)
        self.assertEqual(res.amount_cents, -200)

    def test_subtraction_currency_mismatch(self):
        m1 = Money(500, "GBP")
        m2 = Money(200, "USD")
        with self.assertRaises(ValueError):
            m1.subtract(m2)

    def test_subtraction_type_error(self):
        m = Money(100, "USD")
        with self.assertRaises(TypeError):
            m.subtract("100")  # type: ignore

    def test_multiplication(self):
        m = Money(1000, "USD")
        res = m.multiply(1.5)
        self.assertEqual(res.amount_cents, 1500)
        self.assertEqual(res.currency, "USD")

    def test_multiplication_rounding(self):
        m = Money(105, "USD")
        res = m.multiply(0.333333)
        self.assertEqual(res.amount_cents, 35)

    def test_multiplication_type_error(self):
        m = Money(100, "USD")
        with self.assertRaises(TypeError):
            m.multiply("2.5")  # type: ignore
        with self.assertRaises(TypeError):
            m.multiply(True)  # type: ignore


class TestMoneyEqualityAndFormatting(unittest.TestCase):
    def test_equals_method(self):
        m1 = Money(1234, "USD")
        m2 = Money(1234, "USD")
        m3 = Money(1234, "EUR")
        m4 = Money(4321, "USD")

        self.assertTrue(m1.equals(m2))
        self.assertFalse(m1.equals(m3))
        self.assertFalse(m1.equals(m4))
        self.assertFalse(m1.equals("not money"))

    def test_dunder_eq(self):
        m1 = Money(500, "JPY")
        m2 = Money(500, "JPY")
        m3 = Money(600, "JPY")

        self.assertEqual(m1, m2)
        self.assertNotEqual(m1, m3)

    def test_to_string_formatting(self):
        self.assertEqual(Money(1234, "USD").to_string(), "$12.34 USD")
        self.assertEqual(Money(5, "EUR").to_string(), "$0.05 EUR")
        self.assertEqual(Money(0, "USD").to_string(), "$0.00 USD")
        self.assertEqual(Money(100, "GBP").to_string(), "$1.00 GBP")
        self.assertEqual(Money(-1234, "USD").to_string(), "-$12.34 USD")
        self.assertEqual(Money(-5, "USD").to_string(), "-$0.05 USD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
