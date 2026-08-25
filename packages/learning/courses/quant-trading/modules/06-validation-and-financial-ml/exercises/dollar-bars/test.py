import unittest
from solution import Bar, Tick, generate_dollar_bars


class TestDollarBars(unittest.TestCase):
    def test_single_bar_aggregation(self):
        # 4 ticks of price 100, volume 25 -> each tick is $2500 -> total = $10,000
        ticks = [
            Tick(1.0, 100.0, 25.0),
            Tick(2.0, 102.0, 25.0),
            Tick(3.0, 99.0, 25.0),
            Tick(4.0, 101.0, 25.0),
        ]
        bars = generate_dollar_bars(ticks, dollar_threshold=10_000.0)
        self.assertEqual(len(bars), 1)

        bar = bars[0]
        self.assertEqual(bar.open, 100.0)
        self.assertEqual(bar.high, 102.0)
        self.assertEqual(bar.low, 99.0)
        self.assertEqual(bar.close, 101.0)
        self.assertEqual(bar.volume, 100.0)
        self.assertEqual(bar.dollar_volume, 10_050.0)  # 2500 + 2550 + 2475 + 2525 = 10050

    def test_multiple_bars(self):
        # 10 ticks, each $1000 -> threshold $2500 -> emits 4 bars (2500, 3000, 3000, 1000 left)
        ticks = [Tick(float(i), 10.0, 100.0) for i in range(10)]
        bars = generate_dollar_bars(ticks, dollar_threshold=2500.0)
        # 3 complete bars emitted (at 3000, 6000, 9000), 10th tick remains unclosed
        self.assertEqual(len(bars), 3)


if __name__ == "__main__":
    unittest.main()
