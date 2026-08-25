import unittest
from solution import calculate_volatility_scaled_momentum


class TestMomentumSignals(unittest.TestCase):
    def test_insufficient_history(self):
        self.assertEqual(calculate_volatility_scaled_momentum([100.0, 101.0], lookback=5), 0.0)

    def test_positive_momentum_with_vol_scaling(self):
        # 10 days of steady upward climb: daily return = 1%
        prices = [100.0 * (1.01**i) for i in range(11)]
        weight = calculate_volatility_scaled_momentum(
            prices, lookback=10, target_vol=0.15, annualized_factor=252.0
        )
        self.assertGreater(weight, 0.0)
        self.assertLessEqual(weight, 1.0)

    def test_negative_momentum(self):
        # 10 days of downward slide
        prices = [100.0 * (0.99**i) for i in range(11)]
        weight = calculate_volatility_scaled_momentum(
            prices, lookback=10, target_vol=0.15, annualized_factor=252.0
        )
        self.assertLess(weight, 0.0)
        self.assertGreaterEqual(weight, -1.0)


if __name__ == "__main__":
    unittest.main()
