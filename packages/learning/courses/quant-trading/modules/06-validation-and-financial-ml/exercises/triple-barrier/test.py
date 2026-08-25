import unittest
from solution import apply_triple_barrier


class TestTripleBarrier(unittest.TestCase):
    def test_profit_take_hit(self):
        # Entry at 100 -> steps to 101 -> 103 (hits 2% upper barrier at 102)
        prices = [100.0, 101.0, 103.0, 100.0]
        labels = apply_triple_barrier(
            prices, pt_pct=0.02, sl_pct=0.02, max_holding_period=3
        )
        self.assertEqual(labels[0], 1)

    def test_stop_loss_hit(self):
        # Entry at 100 -> steps to 99 -> 97 (hits 2% lower barrier at 98)
        prices = [100.0, 99.0, 97.0, 105.0]
        labels = apply_triple_barrier(
            prices, pt_pct=0.02, sl_pct=0.02, max_holding_period=3
        )
        self.assertEqual(labels[0], -1)

    def test_vertical_timeout(self):
        # Entry at 100 -> fluctuates between 99.5 and 100.5 -> reaches max holding period
        prices = [100.0, 100.1, 99.9, 100.2, 100.0]
        labels = apply_triple_barrier(
            prices, pt_pct=0.02, sl_pct=0.02, max_holding_period=3
        )
        self.assertEqual(labels[0], 0)


if __name__ == "__main__":
    unittest.main()
