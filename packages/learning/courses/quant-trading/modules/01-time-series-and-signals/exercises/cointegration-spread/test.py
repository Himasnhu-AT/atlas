import unittest
from solution import calculate_spread_zscore


class TestCointegrationSpread(unittest.TestCase):
    def test_exact_linear_relationship(self):
        # Y = 10.0 + 2.0 * X
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [12.0, 14.0, 16.0, 18.0, 20.0]

        res = calculate_spread_zscore(y, x)
        self.assertAlmostEqual(res["beta"], 2.0, places=5)
        self.assertAlmostEqual(res["alpha"], 10.0, places=5)
        for r in res["residuals"]:
            self.assertAlmostEqual(r, 0.0, places=5)
        self.assertAlmostEqual(res["z_score"], 0.0, places=5)

    def test_spread_zscore_divergence(self):
        x = [10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0, 20.0, 20.0, 20.0]
        # Y with a large positive spike at the end
        y = [20.0, 19.8, 20.2, 20.1, 19.9, 40.0, 39.9, 40.1, 40.0, 45.0]

        res = calculate_spread_zscore(y, x)
        self.assertAlmostEqual(res["beta"], 2.0, delta=0.5)
        # Latest z-score must be strongly positive due to the spike to 45.0
        self.assertGreater(res["z_score"], 1.5)

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            calculate_spread_zscore([1.0], [1.0])
        with self.assertRaises(ValueError):
            calculate_spread_zscore([1.0, 2.0], [1.0])
        with self.assertRaises(ZeroDivisionError):
            calculate_spread_zscore([1.0, 2.0], [5.0, 5.0])


if __name__ == "__main__":
    unittest.main()
