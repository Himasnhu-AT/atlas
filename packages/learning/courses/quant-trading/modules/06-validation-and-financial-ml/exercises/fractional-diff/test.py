import unittest
from solution import fractional_differentiation


class TestFractionalDifferentiation(unittest.TestCase):
    def test_d_zero_identity(self):
        prices = [100.0, 102.0, 101.0, 105.0]
        res = fractional_differentiation(prices, d=0.0)
        self.assertEqual(res, prices)

    def test_d_one_integer_difference(self):
        prices = [100.0, 105.0, 102.0, 108.0]
        res = fractional_differentiation(prices, d=1.0)
        # First difference: [100.0, 5.0, -3.0, 6.0]
        self.assertAlmostEqual(res[0], 100.0)
        self.assertAlmostEqual(res[1], 5.0)
        self.assertAlmostEqual(res[2], -3.0)
        self.assertAlmostEqual(res[3], 6.0)

    def test_fractional_d_weights(self):
        prices = [100.0] * 10
        res = fractional_differentiation(prices, d=0.5, threshold=1e-4)
        self.assertEqual(len(res), 10)
        self.assertAlmostEqual(res[0], 100.0)
        # As more constant history accumulates under d=0.5, sum of weights decays toward 0
        self.assertLess(res[-1], res[0])


if __name__ == "__main__":
    unittest.main()
