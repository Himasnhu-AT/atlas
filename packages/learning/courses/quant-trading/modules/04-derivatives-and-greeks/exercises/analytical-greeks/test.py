import unittest
from solution import calculate_greeks


class TestAnalyticalGreeks(unittest.TestCase):
    def test_standard_atm_call_greeks(self):
        g = calculate_greeks(
            spot=100.0,
            strike=100.0,
            tau=1.0,
            r=0.05,
            sigma=0.20,
            is_call=True,
        )

        # Call Delta ATM is approx 0.6368
        self.assertAlmostEqual(g.delta, 0.6368, places=3)
        # Gamma > 0
        self.assertGreater(g.gamma, 0.0)
        self.assertAlmostEqual(g.gamma, 0.01876, places=4)
        # Vega > 0
        self.assertGreater(g.vega, 0.0)
        self.assertAlmostEqual(g.vega, 0.3752, places=3)
        # Theta < 0 (decay)
        self.assertLess(g.theta, 0.0)
        # Rho > 0 for call
        self.assertGreater(g.rho, 0.0)

    def test_standard_atm_put_greeks(self):
        g_call = calculate_greeks(
            spot=100.0, strike=100.0, tau=1.0, r=0.05, sigma=0.20, is_call=True
        )
        g_put = calculate_greeks(
            spot=100.0, strike=100.0, tau=1.0, r=0.05, sigma=0.20, is_call=False
        )

        # Call Delta - Put Delta = 1.0
        self.assertAlmostEqual(g_call.delta - g_put.delta, 1.0, places=5)
        # Gamma and Vega are identical
        self.assertAlmostEqual(g_call.gamma, g_put.gamma, places=6)
        self.assertAlmostEqual(g_call.vega, g_put.vega, places=6)


if __name__ == "__main__":
    unittest.main()
