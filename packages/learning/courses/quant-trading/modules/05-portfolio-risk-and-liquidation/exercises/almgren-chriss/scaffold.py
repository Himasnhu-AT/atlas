from __future__ import annotations

import math


def almgren_chriss_trajectory(
    total_shares: float,
    num_intervals: int,
    tau: float,
    sigma: float,
    eta: float,
    lambda_risk: float,
) -> list[float]:
    """
    Calculate the Almgren-Chriss optimal liquidation inventory trajectory.

    total_shares: initial inventory X (> 0)
    num_intervals: number of execution intervals N (> 0)
    tau: duration of each interval dt (> 0)
    sigma: asset volatility (> 0)
    eta: temporary market impact parameter (> 0)
    lambda_risk: risk-aversion parameter (>= 0)

    Returns a list of length N + 1 with remaining shares at steps k = 0, 1, ..., N.
    """
    raise NotImplementedError
