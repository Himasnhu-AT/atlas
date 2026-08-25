import unittest
from solution import EventBacktester, MarketDataEvent, PortfolioLedger, SignalEvent


class TestEventBacktester(unittest.TestCase):
    def test_buy_and_hold_backtest(self):
        backtester = EventBacktester(
            initial_cash=100_000.0,
            commission_bps=0.0,
            min_commission=0.0,
            slippage_bps=0.0,
        )

        ticks = [
            MarketDataEvent(1.0, "SPY", 100.0, 100.0, 10000.0),
            MarketDataEvent(2.0, "SPY", 110.0, 110.0, 10000.0),
            MarketDataEvent(3.0, "SPY", 120.0, 120.0, 10000.0),
        ]

        def buy_and_hold_strategy(
            md: MarketDataEvent, ledger: PortfolioLedger
        ) -> list[SignalEvent]:
            if md.timestamp == 1.0:
                return [SignalEvent(md.timestamp, "SPY", 1.0)]  # 100% allocation
            return []

        curve = backtester.run(ticks, buy_and_hold_strategy)
        self.assertEqual(len(curve), 3)

        # On tick 1: bought 1000 shares at 100 -> Equity = 100,000
        self.assertAlmostEqual(curve[0]["equity"], 100_000.0, places=2)
        # On tick 2: price is 110 -> 1000 * 110 = 110,000
        self.assertAlmostEqual(curve[1]["equity"], 110_000.0, places=2)
        # On tick 3: price is 120 -> 1000 * 120 = 120,000
        self.assertAlmostEqual(curve[2]["equity"], 120_000.0, places=2)


if __name__ == "__main__":
    unittest.main()
