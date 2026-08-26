import unittest
from solution import calculate_performance_ratios


class TestPerformanceMetrics(unittest.TestCase):
    def test_steady_positive_returns(self):
        # 10 positive returns, 1% daily
        returns = [0.01] * 10
        # Zero variance -> Sharpe = 0.0 (or infinite if unhandled, handled as 0)
        res = calculate_performance_ratios(returns, rf_per_period=0.0)
        self.assertEqual(res["sharpe"], 0.0)

    def test_insufficient_history(self):
        expected = {"sharpe": 0.0, "sortino": 0.0}
        self.assertEqual(calculate_performance_ratios([]), expected)
        self.assertEqual(calculate_performance_ratios([0.01]), expected)

    def test_known_excess_return_ratio(self):
        res = calculate_performance_ratios(
            [0.01, 0.03], rf_per_period=0.01, annualized_factor=1.0
        )
        self.assertAlmostEqual(res["sharpe"], 1.0, places=12)

    def test_no_downside_gives_finite_sortino(self):
        res = calculate_performance_ratios(
            [0.01, 0.03], rf_per_period=0.005, mar=0.01, annualized_factor=1.0
        )
        self.assertGreater(res["sortino"], 0.0)

    def test_skewed_returns_sortino_exceeds_sharpe(self):
        # Returns with small losses but large gains (positive skew)
        returns = [-0.005, -0.005, 0.02, 0.03, 0.04, -0.005, 0.02, 0.05]
        res = calculate_performance_ratios(returns, rf_per_period=0.0, mar=0.0)

        # Both ratios should be positive
        self.assertGreater(res["sharpe"], 0.0)
        self.assertGreater(res["sortino"], 0.0)
        # Because upside volatility is large, Sortino should exceed Sharpe
        self.assertGreater(res["sortino"], res["sharpe"])


if __name__ == "__main__":
    unittest.main()
