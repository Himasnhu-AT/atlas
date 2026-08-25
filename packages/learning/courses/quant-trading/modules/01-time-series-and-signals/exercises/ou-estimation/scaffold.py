from __future__ import annotations

import math


def estimate_ou_parameters(series: list[float], dt: float = 1.0) -> dict[str, float]:
    """
    Estimate continuous Ornstein-Uhlenbeck parameters from a discrete series.

    Returns a dict with:
        "theta": rate of mean reversion
        "mu": long-term equilibrium mean
        "sigma": volatility of the process
        "half_life": half-life of mean reversion in time units

    Raises ValueError if series has fewer than 3 points, if dt <= 0,
    or if the estimated AR(1) slope is not in (0, 1).
    """
    raise NotImplementedError
