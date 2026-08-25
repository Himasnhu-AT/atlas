import unittest
from solution import construct_dollar_neutral_weights


class TestFactorRebalancer(unittest.TestCase):
    def test_six_asset_universe_top_two(self):
        scores = {
            "AAPL": 1.5,
            "MSFT": 0.8,
            "GOOG": 0.2,
            "AMZN": -0.1,
            "META": -0.9,
            "TSLA": -2.0,
        }

        weights = construct_dollar_neutral_weights(scores, top_n=2)

        # Top 2: AAPL (+0.25), MSFT (+0.25)
        # Bottom 2: TSLA (-0.25), META (-0.25)
        # Middle 2: GOOG (0.0), AMZN (0.0)
        self.assertAlmostEqual(weights["AAPL"], 0.25)
        self.assertAlmostEqual(weights["MSFT"], 0.25)
        self.assertAlmostEqual(weights["TSLA"], -0.25)
        self.assertAlmostEqual(weights["META"], -0.25)
        self.assertAlmostEqual(weights["GOOG"], 0.0)
        self.assertAlmostEqual(weights["AMZN"], 0.0)

        # Dollar neutral check (sum == 0)
        self.assertAlmostEqual(sum(weights.values()), 0.0)
        # Gross exposure check (sum of abs == 1)
        self.assertAlmostEqual(sum(abs(w) for w in weights.values()), 1.0)

    def test_invalid_top_n(self):
        scores = {"AAPL": 1.0, "MSFT": 0.5, "GOOG": -0.5}
        with self.assertRaises(ValueError):
            construct_dollar_neutral_weights(scores, top_n=2)  # 2*2 = 4 > 3
        with self.assertRaises(ValueError):
            construct_dollar_neutral_weights(scores, top_n=0)


if __name__ == "__main__":
    unittest.main()
