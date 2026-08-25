import unittest
from solution import calculate_deflated_sharpe


class TestDeflatedSharpe(unittest.TestCase):
    def test_single_trial_strong_sharpe(self):
        # 1 trial, Sharpe 2.0 over 252 days -> very high confidence (DSR > 0.99)
        res = calculate_deflated_sharpe(sharpe=2.0, num_trials=1, sample_length=252)
        self.assertEqual(res["expected_max_sharpe"], 0.0)
        self.assertGreater(res["dsr"], 0.99)

    def test_data_mined_sharpe_deflation(self):
        # Testing 1000 strategy variations until finding a Sharpe of 2.0
        # Expected max Sharpe for N=1000 is ~3.9
        # Therefore DSR collapses to statistically insignificant
        res = calculate_deflated_sharpe(sharpe=2.0, num_trials=1000, sample_length=252)
        self.assertGreater(res["expected_max_sharpe"], 3.5)
        self.assertLess(res["dsr"], 0.05)


if __name__ == "__main__":
    unittest.main()
