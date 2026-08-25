from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(slots=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float  # Per 1% vol shift
    theta: float  # Per 1 calendar day decay
    rho: float  # Per 1% interest rate shift


def calculate_greeks(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
    is_call: bool = True,
) -> Greeks:
    """
    Calculate analytical Black-Scholes price and Greeks.
    """
    raise NotImplementedError
