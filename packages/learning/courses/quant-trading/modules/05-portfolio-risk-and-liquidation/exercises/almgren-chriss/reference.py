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
    if total_shares <= 0 or num_intervals <= 0 or tau <= 0:
        raise ValueError("total_shares, num_intervals, and tau must be strictly positive")
    if sigma <= 0 or eta <= 0:
        raise ValueError("sigma and eta must be strictly positive")
    if lambda_risk < 0:
        raise ValueError("lambda_risk must be non-negative")

    N = num_intervals
    T = N * tau

    if lambda_risk <= 1e-12:
        # Linear TWAP execution
        return [total_shares * (1.0 - k / N) for k in range(N + 1)]

    kappa_sq = (lambda_risk * sigma * sigma) / eta
    kappa = math.sqrt(kappa_sq)

    sinh_kappa_T = math.sinh(kappa * T)
    if sinh_kappa_T <= 1e-12:
        return [total_shares * (1.0 - k / N) for k in range(N + 1)]

    trajectory: list[float] = []
    for k in range(N + 1):
        t_rem = T - k * tau
        val = total_shares * (math.sinh(kappa * t_rem) / sinh_kappa_T)
        trajectory.append(max(0.0, val))

    # Clean exact zero boundary at expiration
    trajectory[-1] = 0.0
    return trajectory
