"""
Tests for: quarantine, not deletion.

Run with `python3 test.py`.
"""

from __future__ import annotations

import math
import unittest

from solution import quarantine_record, rate_moved, summarise_quarantine

RESULT = {
    "row": 6,
    "valid": False,
    "values": {"order_id": 1006, "quantity": None},
    "errors": [{"field": "quantity", "value": "unknown", "problem": "invalid"}],
}
RAW = {"order_id": "1006", "customer": "mei@example.com", "quantity": "unknown"}


class TestQuarantineRecord(unittest.TestCase):
    def setUp(self):
        self.record = quarantine_record(
            RESULT, RAW, "orders_2026-03-06.csv", "2026-03-06T02:00:00Z"
        )

    def test_carries_where_and_when(self):
        self.assertEqual(self.record["row_number"], 6)
        self.assertEqual(self.record["source"], "orders_2026-03-06.csv")
        self.assertEqual(self.record["received_at"], "2026-03-06T02:00:00Z")

    def test_keeps_the_errors(self):
        self.assertEqual(self.record["errors"], RESULT["errors"])

    def test_keeps_the_raw_row_untouched(self):
        self.assertEqual(
            self.record["raw"],
            RAW,
            "the raw row is what makes a quarantine repairable when somebody "
            "fixes the source",
        )

    def test_stores_a_copy_of_the_row(self):
        record = quarantine_record(RESULT, RAW, "s", "t")
        record["raw"]["quantity"] = "TAMPERED"
        self.assertEqual(
            RAW["quantity"],
            "unknown",
            "a quarantine that shares objects with the pipeline is one careless "
            "mutation away from being wrong about what arrived",
        )

    def test_stores_a_copy_of_the_errors(self):
        record = quarantine_record(RESULT, RAW, "s", "t")
        record["errors"][0]["problem"] = "TAMPERED"
        self.assertEqual(RESULT["errors"][0]["problem"], "invalid")


class TestSummarise(unittest.TestCase):
    def setUp(self):
        self.records = [
            {
                "source": "a.csv",
                "errors": [
                    {"field": "quantity", "value": "x", "problem": "invalid"},
                    {"field": "status", "value": None, "problem": "missing"},
                ],
            },
            {
                "source": "a.csv",
                "errors": [{"field": "quantity", "value": "y", "problem": "invalid"}],
            },
            {
                "source": "b.csv",
                "errors": [{"field": "customer", "value": "", "problem": "missing"}],
            },
        ]

    def test_counts_records(self):
        self.assertEqual(summarise_quarantine(self.records)["total"], 3)

    def test_counts_errors_not_rows(self):
        summary = summarise_quarantine(self.records)
        self.assertEqual(summary["by_field"], {"quantity": 2, "status": 1, "customer": 1})
        self.assertEqual(
            summary["by_problem"],
            {"invalid": 2, "missing": 2},
            "this summary is for deciding what to fix, so it counts problems",
        )

    def test_lists_sources_sorted_and_unique(self):
        self.assertEqual(summarise_quarantine(self.records)["sources"], ["a.csv", "b.csv"])

    def test_an_empty_quarantine_summarises_to_zero(self):
        summary = summarise_quarantine([])
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["by_field"], {})
        self.assertEqual(summary["sources"], [])


class TestRateMoved(unittest.TestCase):
    def test_a_steady_rate_has_not_moved(self):
        result = rate_moved({"broken": 2, "total": 10000}, {"broken": 3, "total": 10000})
        self.assertFalse(result["moved"])

    def test_a_jump_has_moved(self):
        result = rate_moved({"broken": 2, "total": 10000}, {"broken": 200, "total": 10000})
        self.assertTrue(result["moved"])
        self.assertAlmostEqual(result["ratio"], 100.0)

    def test_reports_both_rates(self):
        result = rate_moved({"broken": 1, "total": 100}, {"broken": 5, "total": 100})
        self.assertAlmostEqual(result["yesterday_rate"], 0.01)
        self.assertAlmostEqual(result["today_rate"], 0.05)

    def test_none_to_some_is_news(self):
        result = rate_moved({"broken": 0, "total": 10000}, {"broken": 5, "total": 10000})
        self.assertTrue(
            result["moved"],
            "going from no failures to some failures is exactly the change "
            "worth reporting",
        )
        self.assertTrue(math.isinf(result["ratio"]))

    def test_none_to_none_is_not_news(self):
        result = rate_moved({"broken": 0, "total": 10000}, {"broken": 0, "total": 10000})
        self.assertFalse(result["moved"])
        self.assertEqual(result["ratio"], 0.0)

    def test_an_empty_day_does_not_raise(self):
        result = rate_moved({"broken": 0, "total": 0}, {"broken": 0, "total": 0})
        self.assertEqual(result["today_rate"], 0.0)
        self.assertFalse(result["moved"])

    def test_honours_the_threshold(self):
        days = ({"broken": 10, "total": 1000}, {"broken": 15, "total": 1000})
        self.assertFalse(rate_moved(*days, threshold=2.0)["moved"])
        self.assertTrue(rate_moved(*days, threshold=1.5)["moved"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
