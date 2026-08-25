import unittest
from solution import ExecutionHandler, FillEvent, MarketDataEvent, OrderEvent, Side


class TestExecutionHandler(unittest.TestCase):
    def setUp(self):
        self.handler = ExecutionHandler(
            commission_bps=10.0,  # 0.1% = 0.0010
            min_commission=2.0,
            slippage_bps=5.0,  # 0.05% = 0.0005
            max_volume_pct=0.20,  # Max 20% of bar volume
        )

    def test_buy_fill_with_slippage_and_commission(self):
        md = MarketDataEvent(
            timestamp=1000.0,
            symbol="SPY",
            bid=400.0,
            ask=400.10,
            volume=10_000.0,
        )
        order = OrderEvent(
            timestamp=1000.0,
            symbol="SPY",
            side=Side.BUY,
            quantity=100.0,
        )

        fill = self.handler.execute_order(order, md)
        self.assertIsNotNone(fill)
        self.assertEqual(fill.quantity, 100.0)

        # Expected fill price: ask * (1 + 0.0005) = 400.10 * 1.0005 = 400.30005
        expected_fill = 400.10 * 1.0005
        self.assertAlmostEqual(fill.fill_price, expected_fill, places=4)

        # Notional = 100 * 400.30005 = 40030.005
        # Commission = max(2.0, 40030.005 * 0.001) = 40.030005
        self.assertAlmostEqual(fill.commission, 40030.005 * 0.001, places=3)
        self.assertAlmostEqual(fill.slippage, (expected_fill - 400.10) * 100.0, places=3)

    def test_volume_participation_cap(self):
        md = MarketDataEvent(
            timestamp=1000.0,
            symbol="SPY",
            bid=400.0,
            ask=400.10,
            volume=500.0,  # 20% cap means max fill is 100 shares
        )
        order = OrderEvent(
            timestamp=1000.0,
            symbol="SPY",
            side=Side.SELL,
            quantity=1000.0,
        )

        fill = self.handler.execute_order(order, md)
        self.assertIsNotNone(fill)
        self.assertEqual(fill.quantity, 100.0)  # Capped at 20% of 500


if __name__ == "__main__":
    unittest.main()
