from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
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

    Invalid limit orders and market quantities must not mutate the book.
    An order ID can be submitted only once. A partially filled taker with remaining
    quantity is still resting and remains cancellable.
    """

    def __init__(self) -> None:
        pass

    def add_limit_order(self, order: Order) -> list[Trade]:
        """
        Insert a limit order. If it crosses existing orders, execute immediately.
        Remaining quantity is posted to the book.
        Reject a non-positive price or quantity by returning no trades.
        """
        raise NotImplementedError

    def execute_market_order(self, side: Side, quantity: float) -> tuple[list[Trade], float]:
        """
        Execute a market order against the book.
        Returns a tuple of (executed_trades, unfilled_quantity).
        Reject a non-positive quantity by returning (no trades, original quantity).
        """
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order by id in O(1) time.
        Returns True if open remainder was removed; False otherwise.
        """
        raise NotImplementedError

    @property
    def best_bid(self) -> float | None:
        """Highest resting buy price, or None if no bids exist."""
        return None

    @property
    def best_ask(self) -> float | None:
        """Lowest resting sell price, or None if no asks exist."""
        return None

    @property
    def mid_price(self) -> float | None:
        """Arithmetic mean of best bid and best ask, or None if either is missing."""
        return None

    @property
    def spread(self) -> float | None:
        """Difference between best ask and best bid, or None if either is missing."""
        return None
