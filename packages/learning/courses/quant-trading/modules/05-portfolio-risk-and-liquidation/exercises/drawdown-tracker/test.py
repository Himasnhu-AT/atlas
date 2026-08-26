import unittest
from solution import calculate_drawdown_metrics


class TestDrawdownTracker(unittest.TestCase):
    def test_monotonic_growth(self):
        curve = [100.0, 105.0, 110.0, 115.0]
        res = calculate_drawdown_metrics(curve)
        self.assertEqual(res["max_drawdown"], 0.0)
        self.assertEqual(res["max_duration"], 0)
        self.assertEqual(res["current_drawdown"], 0.0)

    def test_drawdown_and_recovery(self):
        # Peak at 100 (t=0) -> 80 (t=1, 20% dd) -> 90 (t=2) -> 100 (t=3, recovers) -> 120 (t=4)
        curve = [100.0, 80.0, 90.0, 100.0, 120.0]
        res = calculate_drawdown_metrics(curve)
        self.assertAlmostEqual(res["max_drawdown"], 0.20, places=4)
        # Duration: from t=0 to t=2 (steps below peak = 2)
        self.assertEqual(res["max_duration"], 2)
        self.assertEqual(res["current_drawdown"], 0.0)

    def test_unrecovered_drawdown(self):
        # Peak at 100 (t=0) -> 90 (t=1) -> 75 (t=2, 25% dd)
        curve = [100.0, 90.0, 75.0]
        res = calculate_drawdown_metrics(curve)
        self.assertAlmostEqual(res["max_drawdown"], 0.25, places=4)
        self.assertEqual(res["max_duration"], 2)
        self.assertAlmostEqual(res["current_drawdown"], 0.25, places=4)

    def test_flat_curve_is_not_underwater(self):
        res = calculate_drawdown_metrics([100.0, 100.0, 100.0])
        self.assertEqual(res["max_drawdown"], 0.0)
        self.assertEqual(res["max_duration"], 0)
        self.assertEqual(res["current_drawdown"], 0.0)

    def test_new_peak_resets_duration(self):
        curve = [100.0, 90.0, 110.0, 105.0]
        res = calculate_drawdown_metrics(curve)
        self.assertAlmostEqual(res["max_drawdown"], 0.10)
        self.assertEqual(res["max_duration"], 1)
        self.assertAlmostEqual(res["current_drawdown"], (110.0 - 105.0) / 110.0)


if __name__ == "__main__":
    unittest.main()
