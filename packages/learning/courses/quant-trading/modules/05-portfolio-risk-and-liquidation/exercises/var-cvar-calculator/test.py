import unittest
from solution import calculate_historical_var_cvar, calculate_parametric_var_cvar


class TestVaRCVaRCalculator(unittest.TestCase):
    def test_historical_var_cvar(self):
        # 100 returns from -0.10 to +0.09 in steps of 0.0019
        returns = [-0.10 + i * 0.002 for i in range(100)]
        var, cvar = calculate_historical_var_cvar(returns, confidence=0.95)

        # 5% of 100 is 5 items: index 0,1,2,3,4
        # index 4 return is -0.10 + 4*0.002 = -0.092 -> VaR = 0.092
        self.assertAlmostEqual(var, 0.092, places=4)
        # CVaR is average of (-0.10, -0.098, -0.096, -0.094, -0.092) = 0.096
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


if __name__ == "__main__":
    unittest.main()
