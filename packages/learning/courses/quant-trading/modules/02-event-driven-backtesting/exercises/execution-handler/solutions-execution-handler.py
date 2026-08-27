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
        if order.quantity <= 0 or md.volume <= 0:
            return None

        max_fillable = md.volume * self.max_volume_pct
        fill_qty = min(order.quantity, max_fillable)
        if fill_qty <= 0:
            return None

        if order.side == Side.BUY:
            base_price = md.ask
            fill_price = base_price * (1.0 + self.slippage_rate)
        else:
            base_price = md.bid
            fill_price = base_price * (1.0 - self.slippage_rate)

        trade_notional = fill_price * fill_qty
        commission = max(self.min_commission, trade_notional * self.commission_rate)
        slippage_cost = abs(fill_price - base_price) * fill_qty

        return FillEvent(
            timestamp=md.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_qty,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage_cost,
        )
