import math
import unittest
from solution import calculate_deflated_sharpe


class TestDeflatedSharpe(unittest.TestCase):
    def test_single_trial_strong_sharpe(self):
        # 1 trial, Sharpe 2.0 over 252 days -> very high confidence (DSR > 0.99)
        res = calculate_deflated_sharpe(sharpe=2.0, num_trials=1, sample_length=252)
        self.assertEqual(res["expected_max_sharpe"], 0.0)
        self.assertGreater(res["dsr"], 0.99)

    def test_data_mined_sharpe_deflation(self):
        # Testing 1000 strategy variations until finding a Sharpe of 2.0.
        # The Bailey/López de Prado benchmark for N=1000 is ~3.2551.
        # Therefore DSR collapses to statistically insignificant
        res = calculate_deflated_sharpe(sharpe=2.0, num_trials=1000, sample_length=252)
        self.assertGreater(res["expected_max_sharpe"], 3.2)
        self.assertLess(res["dsr"], 0.05)

    def test_benchmark_and_probability_are_deterministic(self):
        gamma_const = 0.5772156649
        normal = __import__("statistics").NormalDist()
        expected_benchmark = (
            (1.0 - gamma_const) * normal.inv_cdf(1.0 - 1.0 / 1000.0)
            + gamma_const * normal.inv_cdf(1.0 - 1.0 / (1000.0 * math.e))
        )
        res = calculate_deflated_sharpe(sharpe=3.9, num_trials=1000, sample_length=252)
        self.assertEqual(
            res["expected_max_sharpe"],
            expected_benchmark,
            "unexpected benchmark for 1000 trials",
        )
        expected_se = math.sqrt(251.0 / (252.0 * 251.0))
        expected_z = (3.9 - expected_benchmark) / expected_se
        self.assertAlmostEqual(res["dsr"], normal.cdf(expected_z), places=12)
        self.assertGreater(res["dsr"], 0.99)

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            calculate_deflated_sharpe(0.0, num_trials=0)
        with self.assertRaises(ValueError):
            calculate_deflated_sharpe(0.0, sample_length=2)

    def test_non_normal_moments_change_standard_error(self):
        normal_result = calculate_deflated_sharpe(0.2, skewness=0.0, kurtosis=3.0)["dsr"]
        skewed_result = calculate_deflated_sharpe(-0.4, skewness=-1.0, kurtosis=6.0)["dsr"]
        self.assertLess(skewed_result, normal_result)


if __name__ == "__main__":
    unittest.main()
