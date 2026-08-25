import unittest
from solution import calculate_effective_spread, calculate_order_imbalance


class TestOrderImbalance(unittest.TestCase):
    def test_effective_spread(self):
        # Trade at 100.20 when midpoint is 100.00
        spread = calculate_effective_spread(100.20, 100.00)
        self.assertAlmostEqual(spread, 0.40, places=5)

        # Trade at midpoint
        self.assertAlmostEqual(calculate_effective_spread(100.0, 100.0), 0.0)

    def test_imbalance_empty_or_zero(self):
        self.assertEqual(calculate_order_imbalance([], []), 0.0)
        self.assertEqual(calculate_order_imbalance([(100.0, 0.0)], [(101.0, 0.0)]), 0.0)

    def test_level1_imbalance(self):
        bids = [(99.0, 300.0)]
        asks = [(101.0, 100.0)]
        # (300 - 100) / (300 + 100) = 200 / 400 = 0.5
        obi = calculate_order_imbalance(bids, asks, depth=1)
        self.assertAlmostEqual(obi, 0.5, places=5)

    def test_multilevel_weighted_imbalance(self):
        bids = [(99.0, 200.0), (98.0, 400.0)]
        asks = [(101.0, 100.0), (102.0, 200.0)]
        # depth = 2:
        # level 0 weight = (2-0)/2 = 1.0; bid=200, ask=100 -> num += 1.0*(100) = 100, den += 1.0*(300) = 300
        # level 1 weight = (2-1)/2 = 0.5; bid=400, ask=200 -> num += 0.5*(200) = 100, den += 0.5*(600) = 300
        # OBI = 200 / 600 = 0.333333...
        obi = calculate_order_imbalance(bids, asks, depth=2)
        self.assertAlmostEqual(obi, 1.0 / 3.0, places=5)


if __name__ == "__main__":
    unittest.main()
