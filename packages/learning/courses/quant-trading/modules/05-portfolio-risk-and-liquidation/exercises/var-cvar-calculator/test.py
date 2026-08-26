import unittest
from solution import calculate_historical_var_cvar, calculate_parametric_var_cvar


class TestVaRCVaRCalculator(unittest.TestCase):
    def test_historical_var_cvar(self):
        # 100 returns from -0.10 to +0.09 in steps of 0.002
        returns = [-0.10 + i * 0.002 for i in range(100)]
        var, cvar = calculate_historical_var_cvar(returns, confidence=0.95)

        # 95% of 100 observations selects the five worst returns: indices 0-4.
        self.assertAlmostEqual(var, 0.092, places=4)
        self.assertAlmostEqual(cvar, 0.096, places=4)
        self.assertGreater(cvar, var)

    def test_parametric_var_cvar(self):
        mean = 0.0
        std = 0.02
        var, cvar = calculate_parametric_var_cvar(mean, std, confidence=0.95)

        # 95% z is approx 1.64485 -> VaR = 1.64485 * 0.02 = 0.032897
        self.assertAlmostEqual(var, 0.032897, places=4)
        # CVaR > VaR
        self.assertGreater(cvar, var)

    def test_historical_tail_count_is_exact(self):
        returns = [-0.01] * 5 + [0.02] * 95
        var, cvar = calculate_historical_var_cvar(returns, confidence=0.95)
        self.assertEqual(var, 0.01, "95% VaR must use exactly the worst 5 observations")
        self.assertEqual(cvar, 0.01, "CVaR must average only the selected loss tail")

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError, msg="empty returns cannot define a distribution"):
            calculate_historical_var_cvar([])
        with self.assertRaises(ValueError, msg="confidence must be an open-interval probability"):
            calculate_historical_var_cvar([0.0], confidence=1.0)
        with self.assertRaises(ValueError, msg="standard deviation cannot be negative"):
            calculate_parametric_var_cvar(0.0, -0.01)


if __name__ == "__main__":
    unittest.main()
