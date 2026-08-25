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
    if dollar_threshold <= 0:
        raise ValueError("dollar_threshold must be strictly positive")

    bars: list[Bar] = []
    if not ticks:
        return bars

    cum_dollars = 0.0
    cum_vol = 0.0
    open_p = 0.0
    high_p = 0.0
    low_p = 0.0
    in_bar = False

    for tick in ticks:
        tick_dollar = tick.price * tick.volume
        if not in_bar:
            open_p = tick.price
            high_p = tick.price
            low_p = tick.price
            cum_dollars = 0.0
            cum_vol = 0.0
            in_bar = True

        high_p = max(high_p, tick.price)
        low_p = min(low_p, tick.price)
        cum_dollars += tick_dollar
        cum_vol += tick.volume

        if cum_dollars >= dollar_threshold:
            bars.append(
                Bar(
                    timestamp=tick.timestamp,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=tick.price,
                    volume=cum_vol,
                    dollar_volume=cum_dollars,
                )
            )
            in_bar = False

    return bars
