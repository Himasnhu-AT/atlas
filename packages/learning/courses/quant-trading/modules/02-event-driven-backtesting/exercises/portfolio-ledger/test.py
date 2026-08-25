import unittest
from solution import FillEvent, PortfolioLedger, Side


class TestPortfolioLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = PortfolioLedger(initial_cash=100_000.0)

    def test_initial_state(self):
        self.assertEqual(self.ledger.cash, 100_000.0)
        self.assertEqual(self.ledger.total_equity({}), 100_000.0)

    def test_buy_and_sell_cycle_with_commission(self):
        # Buy 100 shares of AAPL at 150 with $2 commission
        fill1 = FillEvent(
            timestamp=1.0,
            symbol="AAPL",
            side=Side.BUY,
            quantity=100.0,
            fill_price=150.0,
            commission=2.0,
        )
        self.ledger.apply_fill(fill1)

        # Cash: 100,000 - 15,000 - 2 = 84,998
        self.assertEqual(self.ledger.cash, 84_998.0)
        pos = self.ledger.get_position("AAPL")
        self.assertEqual(pos.quantity, 100.0)
        self.assertEqual(pos.avg_entry_price, 150.0)

        # Mark-to-market when price moves to 160: Cash (84,998) + MV (100 * 160 = 16,000) = 100,998
        self.assertEqual(self.ledger.total_equity({"AAPL": 160.0}), 100_998.0)

        # Sell 100 shares of AAPL at 160 with $2 commission
        fill2 = FillEvent(
            timestamp=2.0,
            symbol="AAPL",
            side=Side.SELL,
            quantity=100.0,
            fill_price=160.0,
            commission=2.0,
        )
        self.ledger.apply_fill(fill2)

        # Cash = 84,998 + 16,000 - 2 = 100,996
        self.assertEqual(self.ledger.cash, 100_996.0)
        self.assertEqual(pos.quantity, 0.0)
        self.assertEqual(pos.realized_pnl, 1_000.0)
        self.assertEqual(self.ledger.total_equity({"AAPL": 160.0}), 100_996.0)

    def test_short_position_accounting(self):
        # Sell short 50 shares of TSLA at 200 with $1 commission
        fill_short = FillEvent(
            timestamp=1.0,
            symbol="TSLA",
            side=Side.SELL,
            quantity=50.0,
            fill_price=200.0,
            commission=1.0,
        )
        self.ledger.apply_fill(fill_short)
        # Cash = 100,000 + 10,000 - 1 = 109,999
        self.assertEqual(self.ledger.cash, 109_999.0)
        pos = self.ledger.get_position("TSLA")
        self.assertEqual(pos.quantity, -50.0)
        self.assertEqual(pos.avg_entry_price, 200.0)

        # Buy to cover at 180 (profit of $20/share = $1000)
        fill_cover = FillEvent(
            timestamp=2.0,
            symbol="TSLA",
            side=Side.BUY,
            quantity=50.0,
            fill_price=180.0,
            commission=1.0,
        )
        self.ledger.apply_fill(fill_cover)
        # Cash = 109,999 - 9,000 - 1 = 100,998
        self.assertEqual(self.ledger.cash, 100_998.0)
        self.assertEqual(pos.quantity, 0.0)
        self.assertEqual(pos.realized_pnl, 1_000.0)


if __name__ == "__main__":
    unittest.main()
