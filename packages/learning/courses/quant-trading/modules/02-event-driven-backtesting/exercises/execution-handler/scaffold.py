from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
    slippage: float


class ExecutionHandler:
    """
    Simulates realistic order execution with slippage, commissions, and volume limits.
    """

    def __init__(
        self,
        commission_bps: float = 5.0,
        min_commission: float = 1.0,
        slippage_bps: float = 2.0,
        max_volume_pct: float = 0.10,
    ) -> None:
        self.commission_rate = commission_bps / 10_000.0
        self.min_commission = min_commission
        self.slippage_rate = slippage_bps / 10_000.0
        self.max_volume_pct = max_volume_pct

    def execute_order(self, order: OrderEvent, md: MarketDataEvent) -> FillEvent | None:
        """
        Execute an order against the prevailing market data.
        Returns a FillEvent, or None if no quantity could be filled.
        """
        raise NotImplementedError
