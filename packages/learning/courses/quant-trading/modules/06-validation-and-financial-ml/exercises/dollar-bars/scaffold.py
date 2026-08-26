from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Tick:
    timestamp: float
    price: float
    volume: float


@dataclass(slots=True, frozen=True)
class Bar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    dollar_volume: float


def generate_dollar_bars(
    ticks: list[Tick],
    dollar_threshold: float,
) -> list[Bar]:
    """
    Aggregate incoming tick stream into fixed dollar-volume OHLCV bars.

    ticks: list of Tick(timestamp, price, volume)
    dollar_threshold: cumulative dollar value (price * volume) required to emit a bar (> 0)
    Tick prices must be positive; tick volumes must be non-negative.

    Returns list of completed Bar objects. A partial final bar is retained.
    """
    raise NotImplementedError
