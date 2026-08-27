from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


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
        trade_cost = fill.fill_price * fill.quantity

        if fill.side == Side.BUY:
            self.cash -= trade_cost + fill.commission
            if pos.quantity >= 0:
                new_qty = pos.quantity + fill.quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * pos.quantity) + trade_cost
                ) / new_qty
                pos.quantity = new_qty
            else:
                closed_qty = min(abs(pos.quantity), fill.quantity)
                pos.realized_pnl += (pos.avg_entry_price - fill.fill_price) * closed_qty
                pos.quantity += fill.quantity
                if pos.quantity > 0:
                    pos.avg_entry_price = fill.fill_price
        else:
            self.cash += trade_cost - fill.commission
            if pos.quantity <= 0:
                new_qty = abs(pos.quantity) + fill.quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * abs(pos.quantity)) + trade_cost
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
