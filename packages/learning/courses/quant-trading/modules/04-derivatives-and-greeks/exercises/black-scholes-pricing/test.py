import math
import unittest
from solution import black_scholes_call, black_scholes_put


class TestBlackScholes(unittest.TestCase):
    def test_standard_atm_option(self):
        s, k, tau, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20
        call = black_scholes_call(s, k, tau, r, sigma)
        put = black_scholes_put(s, k, tau, r, sigma)

        # Theoretical textbook values
        self.assertAlmostEqual(call, 10.45058, places=3)
        self.assertAlmostEqual(put, 5.57353, places=3)

        # Put-Call Parity: C - P = S - K * exp(-r * T)
        expected_diff = s - k * math.exp(-r * tau)
        self.assertAlmostEqual(call - put, expected_diff, places=5)

    def test_zero_time_to_maturity(self):
        # Immediate expiration intrinsic value
        self.assertEqual(black_scholes_call(110.0, 100.0, 0.0, 0.05, 0.20), 10.0)
        self.assertEqual(black_scholes_call(90.0, 100.0, 0.0, 0.05, 0.20), 0.0)
        self.assertEqual(black_scholes_put(90.0, 100.0, 0.0, 0.05, 0.20), 10.0)


if __name__ == "__main__":
    unittest.main()
