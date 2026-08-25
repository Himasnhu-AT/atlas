import unittest
from solution import Order, OrderBook, Side, Trade


class TestLimitOrderBook(unittest.TestCase):
    def setUp(self):
        self.book = OrderBook()

    def test_empty_book(self):
        self.assertIsNone(self.book.best_bid)
        self.assertIsNone(self.book.best_ask)
        self.assertIsNone(self.book.mid_price)
        self.assertIsNone(self.book.spread)

    def test_add_passive_orders(self):
        self.book.add_limit_order(Order("o1", Side.BUY, 99.0, 100.0))
        self.book.add_limit_order(Order("o2", Side.BUY, 99.5, 50.0))
        self.book.add_limit_order(Order("o3", Side.SELL, 100.5, 75.0))
        self.book.add_limit_order(Order("o4", Side.SELL, 101.0, 120.0))

        self.assertEqual(self.book.best_bid, 99.5)
        self.assertEqual(self.book.best_ask, 100.5)
        self.assertEqual(self.book.mid_price, 100.0)
        self.assertEqual(self.book.spread, 1.0)

    def test_crossing_limit_order(self):
        self.book.add_limit_order(Order("ask1", Side.SELL, 100.0, 50.0))
        self.book.add_limit_order(Order("ask2", Side.SELL, 101.0, 50.0))

        # Aggressive buy crossing the 100.0 ask and taking 30 shares
        trades = self.book.add_limit_order(Order("buy1", Side.BUY, 100.0, 30.0))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, 100.0)
        self.assertEqual(trades[0].quantity, 30.0)
        self.assertEqual(self.book.best_ask, 100.0)

        # Aggressive buy eating remaining 20 shares at 100.0 + 10 shares at 101.0
        trades2 = self.book.add_limit_order(Order("buy2", Side.BUY, 101.0, 30.0))
        self.assertEqual(len(trades2), 2)
        self.assertEqual(trades2[0].price, 100.0)
        self.assertEqual(trades2[0].quantity, 20.0)
        self.assertEqual(trades2[1].price, 101.0)
        self.assertEqual(trades2[1].quantity, 10.0)
        self.assertEqual(self.book.best_ask, 101.0)

    def test_market_order_execution(self):
        self.book.add_limit_order(Order("b1", Side.BUY, 100.0, 40.0))
        self.book.add_limit_order(Order("b2", Side.BUY, 99.0, 60.0))

        trades, unfilled = self.book.execute_market_order(Side.SELL, 70.0)
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].price, 100.0)
        self.assertEqual(trades[0].quantity, 40.0)
        self.assertEqual(trades[1].price, 99.0)
        self.assertEqual(trades[1].quantity, 30.0)
        self.assertEqual(unfilled, 0.0)
        self.assertEqual(self.book.best_bid, 99.0)

    def test_cancel_order(self):
        self.book.add_limit_order(Order("b1", Side.BUY, 100.0, 50.0))
        self.assertEqual(self.book.best_bid, 100.0)

        self.assertTrue(self.book.cancel_order("b1"))
        self.assertFalse(self.book.cancel_order("non_existent"))

        # Market order should not match cancelled order
        trades, unfilled = self.book.execute_market_order(Side.SELL, 50.0)
        self.assertEqual(len(trades), 0)
        self.assertEqual(unfilled, 50.0)


if __name__ == "__main__":
    unittest.main()
