import unittest
from solution import generate_pairs_signals


class TestPairsStrategy(unittest.TestCase):
    def test_entry_from_flat(self):
        # Neutral z-score -> stay flat
        self.assertEqual(generate_pairs_signals(0.2, current_position=0), 0)
        # Undervalued spread -> Long Spread (+1)
        self.assertEqual(generate_pairs_signals(-2.1, current_position=0), 1)
        # Overvalued spread -> Short Spread (-1)
        self.assertEqual(generate_pairs_signals(2.3, current_position=0), -1)

    def test_long_spread_exit_and_stop(self):
        # Still widening within limits -> hold long
        self.assertEqual(generate_pairs_signals(-1.5, current_position=1), 1)
        # Mean reversion past -0.5 -> exit to flat
        self.assertEqual(generate_pairs_signals(-0.4, current_position=1), 0)
        # Stop loss breach past -3.5 -> exit to flat
        self.assertEqual(generate_pairs_signals(-3.6, current_position=1), 0)

    def test_short_spread_exit_and_stop(self):
        # Still widening within limits -> hold short
        self.assertEqual(generate_pairs_signals(1.5, current_position=-1), -1)
        # Mean reversion below +0.5 -> exit to flat
        self.assertEqual(generate_pairs_signals(0.3, current_position=-1), 0)
        # Stop loss breach past +3.5 -> exit to flat
        self.assertEqual(generate_pairs_signals(3.8, current_position=-1), 0)


if __name__ == "__main__":
    unittest.main()
