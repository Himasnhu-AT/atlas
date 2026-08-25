"""
Course support library for Quantitative Trading.

Provides deterministic mathematical functions and market data generators
using the Python standard library alone. Copied into every exercise workspace.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterator, Sequence


def norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function via math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_inv_cdf(p: float) -> float:
    """Inverse standard normal cumulative distribution function."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability p must be in (0, 1)")
    return statistics.NormalDist(mu=0.0, sigma=1.0).inv_cdf(p)


@dataclass(slots=True, frozen=True)
class Tick:
    timestamp: float
    symbol: str
    price: float
    volume: float
    bid: float
    ask: float


def generate_synthetic_gbm(
    s0: float = 100.0,
    mu: float = 0.05,
    sigma: float = 0.20,
    n_steps: int = 252,
    dt: float = 1.0 / 252.0,
    seed: int = 42,
) -> list[float]:
    """
    Generate a deterministic Geometric Brownian Motion price series.
    S_t = S_0 * exp((mu - 0.5 * sigma^2) * t + sigma * W_t)
    """
    rng = random.Random(seed)
    prices = [s0]
    drift = (mu - 0.5 * sigma * sigma) * dt
    vol_step = sigma * math.sqrt(dt)

    current_price = s0
    for _ in range(n_steps):
        # Box-Muller transform for deterministic standard normal sample
        u1 = max(1e-12, rng.random())
        u2 = rng.random()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        current_price *= math.exp(drift + vol_step * z)
        prices.append(round(current_price, 4))

    return prices


def generate_synthetic_ou(
    x0: float = 0.0,
    theta: float = 5.0,
    mu: float = 0.0,
    sigma: float = 1.0,
    n_steps: int = 500,
    dt: float = 1.0 / 252.0,
    seed: int = 42,
) -> list[float]:
    """
    Generate a deterministic Ornstein-Uhlenbeck mean-reverting path.
    dx_t = theta * (mu - x_t) * dt + sigma * dW_t
    """
    rng = random.Random(seed)
    values = [x0]
    curr = x0
    vol_step = sigma * math.sqrt(dt)

    for _ in range(n_steps):
        u1 = max(1e-12, rng.random())
        u2 = rng.random()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        curr += theta * (mu - curr) * dt + vol_step * z
        values.append(round(curr, 6))

    return values


def generate_synthetic_ticks(
    symbol: str = "AAPL",
    s0: float = 150.0,
    n_ticks: int = 200,
    spread: float = 0.02,
    seed: int = 42,
) -> list[Tick]:
    """Generate a deterministic stream of tick data with bid-ask quotes."""
    rng = random.Random(seed)
    ticks: list[Tick] = []
    price = s0
    t = 1700000000.0

    for _ in range(n_ticks):
        delta = (rng.random() - 0.49) * 0.10
        price = max(1.0, price + delta)
        vol = round(rng.uniform(10.0, 500.0), 2)
        half_spread = spread / 2.0
        bid = round(price - half_spread, 2)
        ask = round(price + half_spread, 2)
        t += round(rng.uniform(0.1, 2.0), 3)
        ticks.append(
            Tick(
                timestamp=round(t, 3),
                symbol=symbol,
                price=round(price, 2),
                volume=vol,
                bid=bid,
                ask=ask,
            )
        )

    return ticks
