import statistics
import unittest
from solution import RollingVariance, StreamingEMA


class TestStreamingStats(unittest.TestCase):
    def test_ema_warmup_and_smoothing(self):
        ema = StreamingEMA(window=3)
        # alpha = 2 / (3 + 1) = 0.5
        v1 = ema.update(10.0)
        self.assertAlmostEqual(v1, 10.0)
        v2 = ema.update(20.0)
        self.assertAlmostEqual(v2, 15.0)  # (10 + 20) / 2
        v3 = ema.update(30.0)
        self.assertAlmostEqual(v3, 20.0)  # (10 + 20 + 30) / 3

        # Next update triggers smoothing: 0.5 * 40 + 0.5 * 20 = 30.0
        v4 = ema.update(40.0)
        self.assertAlmostEqual(v4, 30.0)

    def test_rolling_variance(self):
        rv = RollingVariance(window=5, annualized_factor=252.0)
        prices = [10.0, 12.0, 11.0, 13.0, 14.0]

        for p in prices[:4]:
            rv.update(p)
        var, vol = rv.update(prices[4])

        expected_var = statistics.variance(prices)
        self.assertAlmostEqual(var, expected_var, places=5)
        self.assertAlmostEqual(vol, (expected_var * 252.0) ** 0.5, places=5)

    def test_rolling_variance_window_slide(self):
        rv = RollingVariance(window=3, annualized_factor=1.0)
        # Push 4 items: [10, 10, 10] then 10 -> variance should be 0.0
        for _ in range(4):
            var, _ = rv.update(100.0)
        self.assertAlmostEqual(var, 0.0)


if __name__ == "__main__":
    unittest.main()
