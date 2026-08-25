from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from enum import Enum
from typing import Callable


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(slots=True, frozen=True)
class MarketDataEvent:
    timestamp: float
    symbol: str
    bid: float
    ask: float
    volume: float


@dataclass(slots=True, frozen=True)
class SignalEvent:
    timestamp: float
    symbol: str
    target_weight: float


@dataclass(slots=True, frozen=True)
class OrderEvent:
    timestamp: float
    symbol: str
    side: Side
    quantity: float


@dataclass(slots=True, frozen=True)
class FillEvent:
    timestamp: float
    symbol: str
    side: Side
    quantity: float
    fill_price: float
    commission: float
    slippage: float = 0.0


@dataclass(slots=True)
class Position:
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0


class PortfolioLedger:
    def __init__(self, initial_cash: float = 100_000.0) -> None:
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position()
        return self.positions[symbol]

    def apply_fill(self, fill: FillEvent) -> None:
        pos = self.get_position(fill.symbol)
        cost = fill.fill_price * fill.quantity

        if fill.side == Side.BUY:
            self.cash -= cost + fill.commission
            if pos.quantity >= 0:
                new_qty = pos.quantity + fill.quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * pos.quantity) + cost
                ) / new_qty
                pos.quantity = new_qty
            else:
                closed_qty = min(abs(pos.quantity), fill.quantity)
                pos.realized_pnl += (pos.avg_entry_price - fill.fill_price) * closed_qty
                pos.quantity += fill.quantity
                if pos.quantity > 0:
                    pos.avg_entry_price = fill.fill_price
        else:
            self.cash += cost - fill.commission
            if pos.quantity <= 0:
                new_qty = abs(pos.quantity) + fill.quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * abs(pos.quantity)) + cost
                ) / new_qty
                pos.quantity = -new_qty
            else:
                closed_qty = min(pos.quantity, fill.quantity)
                pos.realized_pnl += (fill.fill_price - pos.avg_entry_price) * closed_qty
                pos.quantity -= fill.quantity
                if pos.quantity < 0:
                    pos.avg_entry_price = fill.fill_price

    def total_equity(self, current_prices: dict[str, float]) -> float:
        market_value = 0.0
        for sym, pos in self.positions.items():
            if pos.quantity != 0 and sym in current_prices:
                market_value += current_prices[sym] * pos.quantity
        return self.cash + market_value


class EventBacktester:
    """
    Deterministic event-driven backtesting engine.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_bps: float = 5.0,
        min_commission: float = 1.0,
        slippage_bps: float = 2.0,
    ) -> None:
        self.initial_cash = initial_cash
        self.commission_rate = commission_bps / 10_000.0
        self.min_commission = min_commission
        self.slippage_rate = slippage_bps / 10_000.0
        self.ledger = PortfolioLedger(initial_cash)

    def run(
        self,
        market_stream: list[MarketDataEvent],
        strategy_fn: Callable[[MarketDataEvent, PortfolioLedger], list[SignalEvent]],
    ) -> list[dict[str, float]]:
        """
        Execute strategy over market data stream and return list of equity curve dicts:
        [{"timestamp": t, "equity": eq, "cash": cash}, ...]
        """
        raise NotImplementedError
