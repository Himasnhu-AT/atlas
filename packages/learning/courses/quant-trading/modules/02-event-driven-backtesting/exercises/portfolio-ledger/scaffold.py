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
    """
    Manages multi-asset positions, cash, and mark-to-market valuations.
    """

    def __init__(self, initial_cash: float = 100_000.0) -> None:
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}

    def get_position(self, symbol: str) -> Position:
        """Return position object for symbol (creates default if missing)."""
        raise NotImplementedError

    def apply_fill(self, fill: FillEvent) -> None:
        """
        Update cash, positions, and realized PnL given a FillEvent.
        """
        raise NotImplementedError

    def total_equity(self, current_prices: dict[str, float]) -> float:
        """
        Calculate total equity: cash + unrealized PnL across all open positions.
        """
        raise NotImplementedError
