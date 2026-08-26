"""
Tests for: coercion and what it costs.

Run with `python3 test.py`.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from sampledata import orders_csv, read_rows

from solution import to_bool, to_date, to_decimal, to_int


class TestToInt(unittest.TestCase):
    def test_reads_an_integer(self):
        self.assertEqual(to_int("42"), (42, True))

    def test_ignores_surrounding_whitespace(self):
        self.assertEqual(to_int(" 42 "), (42, True))

    def test_reads_a_sign(self):
        self.assertEqual(to_int("-3"), (-3, True))

    def test_a_word_fails(self):
        self.assertEqual(to_int("unknown"), (None, False))

    def test_empty_fails(self):
        self.assertEqual(to_int(""), (None, False))

    def test_absent_fails(self):
        self.assertEqual(to_int(None), (None, False))

    def test_a_decimal_fails_rather_than_truncating(self):
        self.assertEqual(
            to_int("2.7"),
            (None, False),
            "2.7 items is not two items, it is a field that does not mean what "
            "you assumed",
        )

    def test_never_returns_a_number_and_false(self):
        for raw in ["1", "x", "", None, " 0 "]:
            value, ok = to_int(raw)
            self.assertEqual(ok, value is not None, f"{raw!r} disagreed with itself")


class TestToDecimal(unittest.TestCase):
    def test_reads_a_plain_amount(self):
        self.assertEqual(to_decimal("29.99"), (Decimal("29.99"), True))

    def test_strips_a_currency_symbol(self):
        self.assertEqual(to_decimal("$59.00"), (Decimal("59.00"), True))

    def test_strips_a_thousands_comma(self):
        self.assertEqual(to_decimal("1,499.00"), (Decimal("1499.00"), True))

    def test_returns_a_decimal_not_a_float(self):
        value, _ = to_decimal("0.10")
        self.assertIsInstance(
            value,
            Decimal,
            "a float cannot hold 0.10 exactly, and the drift shows up as a "
            "total that is out by a cent in a report somebody has to explain",
        )

    def test_keeps_the_value_exact(self):
        a, _ = to_decimal("0.10")
        b, _ = to_decimal("0.20")
        self.assertEqual(a + b, Decimal("0.30"))

    def test_a_word_fails(self):
        self.assertEqual(to_decimal("free"), (None, False))

    def test_empty_and_absent_fail(self):
        self.assertEqual(to_decimal(""), (None, False))
        self.assertEqual(to_decimal(None), (None, False))

    def test_a_currency_symbol_alone_is_not_zero(self):
        self.assertEqual(to_decimal("$"), (None, False))

    def test_a_sign_alone_is_not_zero(self):
        self.assertEqual(to_decimal("-"), (None, False))


class TestToDate(unittest.TestCase):
    def test_reads_iso(self):
        self.assertEqual(to_date("2026-03-01"), ("2026-03-01", True))

    def test_reads_a_timestamp_and_keeps_the_date(self):
        self.assertEqual(to_date("2026-03-02T09:14:00"), ("2026-03-02", True))

    def test_reads_slashes_day_first_by_default(self):
        self.assertEqual(to_date("01/03/2026"), ("2026-03-01", True))

    def test_reads_slashes_month_first_when_told_to(self):
        self.assertEqual(
            to_date("01/03/2026", day_first=False),
            ("2026-01-03", True),
            "nothing in the file says which reading is right, so the caller "
            "decides and the decision is visible",
        )

    def test_a_date_that_does_not_exist_fails(self):
        self.assertEqual(
            to_date("31/02/2026"),
            (None, False),
            "rolling into March would invent a day the source never sent",
        )

    def test_nonsense_fails(self):
        self.assertEqual(to_date("last tuesday"), (None, False))
        self.assertEqual(to_date(""), (None, False))
        self.assertEqual(to_date(None), (None, False))

    def test_reads_every_spelling_in_the_extract(self):
        rows = read_rows(orders_csv())
        readable = sum(1 for row in rows if to_date(row["placed_at"])[1])
        self.assertEqual(
            readable, len(rows), "every row in the sample has a readable date"
        )


class TestToBool(unittest.TestCase):
    def test_reads_the_true_spellings(self):
        for raw in ["true", "TRUE", " t ", "yes", "y", "1"]:
            self.assertEqual(to_bool(raw), (True, True), raw)

    def test_reads_the_false_spellings(self):
        for raw in ["false", "F", "no", "n", "0"]:
            self.assertEqual(to_bool(raw), (False, True), raw)

    def test_empty_is_not_false(self):
        self.assertEqual(
            to_bool(""),
            (None, False),
            "an empty boolean is a question nobody answered, and reading it as "
            "False invents a 'no' the source never sent",
        )

    def test_absent_is_not_false(self):
        self.assertEqual(to_bool(None), (None, False))

    def test_a_word_fails(self):
        self.assertEqual(to_bool("maybe"), (None, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
