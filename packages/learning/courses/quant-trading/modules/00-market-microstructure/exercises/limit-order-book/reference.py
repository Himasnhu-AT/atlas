from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import bisect
import time


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(slots=True)
class Order:
    order_id: str
    side: Side
    price: float
    quantity: float
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class Trade:
    taker_order_id: str
    maker_order_id: str
    side: Side
    price: float
    quantity: float
    timestamp: float = field(default_factory=time.time)


class OrderBook:
    """
    In-memory limit order book with price-time priority.
    """

    def __init__(self) -> None:
        self._bids_prices: list[float] = []
        self._bids_levels: dict[float, deque[Order]] = {}
        self._asks_prices: list[float] = []
        self._asks_levels: dict[float, deque[Order]] = {}
        self._orders: dict[str, Order] = {}

    def add_limit_order(self, order: Order) -> list[Trade]:
        trades: list[Trade] = []
        if order.quantity <= 0 or order.price <= 0:
            return trades

        if order.side == Side.BUY:
            while self._asks_prices and order.quantity > 0:
                best_ask = self._asks_prices[0]
                if order.price < best_ask:
                    break
                queue = self._asks_levels[best_ask]
                while queue and order.quantity > 0:
                    maker = queue[0]
                    if maker.quantity <= 0:
                        queue.popleft()
                        continue
                    matched = min(order.quantity, maker.quantity)
                    trades.append(
                        Trade(
                            taker_order_id=order.order_id,
                            maker_order_id=maker.order_id,
                            side=Side.BUY,
                            price=best_ask,
                            quantity=matched,
                        )
                    )
                    order.quantity -= matched
                    maker.quantity -= matched
                    if maker.quantity == 0:
                        queue.popleft()
                        self._orders.pop(maker.order_id, None)

                if not queue:
                    del self._asks_levels[best_ask]
                    self._asks_prices.pop(0)

            if order.quantity > 0:
                self._orders[order.order_id] = order
                if order.price not in self._bids_levels:
                    bisect.insort(self._bids_prices, order.price)
                    self._bids_levels[order.price] = deque()
                self._bids_levels[order.price].append(order)

        else:
            while self._bids_prices and order.quantity > 0:
                best_bid = self._bids_prices[-1]
                if order.price > best_bid:
                    break
                queue = self._bids_levels[best_bid]
                while queue and order.quantity > 0:
                    maker = queue[0]
                    if maker.quantity <= 0:
                        queue.popleft()
                        continue
                    matched = min(order.quantity, maker.quantity)
                    trades.append(
                        Trade(
                            taker_order_id=order.order_id,
                            maker_order_id=maker.order_id,
                            side=Side.SELL,
                            price=best_bid,
                            quantity=matched,
                        )
                    )
                    order.quantity -= matched
                    maker.quantity -= matched
                    if maker.quantity == 0:
                        queue.popleft()
                        self._orders.pop(maker.order_id, None)

                if not queue:
                    del self._bids_levels[best_bid]
                    self._bids_prices.pop()

            if order.quantity > 0:
                self._orders[order.order_id] = order
                if order.price not in self._asks_levels:
                    bisect.insort(self._asks_prices, order.price)
                    self._asks_levels[order.price] = deque()
                self._asks_levels[order.price].append(order)

        return trades

    def execute_market_order(self, side: Side, quantity: float) -> tuple[list[Trade], float]:
        trades: list[Trade] = []
        remaining = quantity

        if side == Side.BUY:
            while self._asks_prices and remaining > 0:
                best_ask = self._asks_prices[0]
                queue = self._asks_levels[best_ask]
                while queue and remaining > 0:
                    maker = queue[0]
                    if maker.quantity <= 0:
                        queue.popleft()
                        continue
                    matched = min(remaining, maker.quantity)
                    trades.append(
                        Trade(
                            taker_order_id="MARKET_BUY",
                            maker_order_id=maker.order_id,
                            side=Side.BUY,
                            price=best_ask,
                            quantity=matched,
                        )
                    )
                    remaining -= matched
                    maker.quantity -= matched
                    if maker.quantity == 0:
                        queue.popleft()
                        self._orders.pop(maker.order_id, None)

                if not queue:
                    del self._asks_levels[best_ask]
                    self._asks_prices.pop(0)
        else:
            while self._bids_prices and remaining > 0:
                best_bid = self._bids_prices[-1]
                queue = self._bids_levels[best_bid]
                while queue and remaining > 0:
                    maker = queue[0]
                    if maker.quantity <= 0:
                        queue.popleft()
                        continue
                    matched = min(remaining, maker.quantity)
                    trades.append(
                        Trade(
                            taker_order_id="MARKET_SELL",
                            maker_order_id=maker.order_id,
                            side=Side.SELL,
                            price=best_bid,
                            quantity=matched,
                        )
                    )
                    remaining -= matched
                    maker.quantity -= matched
                    if maker.quantity == 0:
                        queue.popleft()
                        self._orders.pop(maker.order_id, None)

                if not queue:
                    del self._bids_levels[best_bid]
                    self._bids_prices.pop()

        return trades, remaining

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.pop(order_id, None)
        if order is None:
            return False
        order.quantity = 0.0
        return True

    @property
    def best_bid(self) -> float | None:
        return self._bids_prices[-1] if self._bids_prices else None

    @property
    def best_ask(self) -> float | None:
        return self._asks_prices[0] if self._asks_prices else None

    @property
    def mid_price(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / 2.0
        return None

    @property
    def spread(self) -> float | None:
        bb, ba = self.best_bid, self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return None
