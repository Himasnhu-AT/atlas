from __future__ import annotations

import math
import statistics


def calculate_historical_var_cvar(
    returns: list[float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    if not returns:
        raise ValueError("returns must contain at least one observation")

    sorted_r = sorted(returns)
    n = len(sorted_r)
    alpha = 1.0 - confidence
    if not 0.0 < alpha < 1.0:
        raise ValueError("confidence must be strictly between 0 and 1")

    # Compensate for tiny binary-fraction overshoots such as
    # 1 - 0.95 producing 0.050000000000000044.
    k = max(1, min(n, math.ceil(alpha * n - 1e-12)))

    var = -sorted_r[k - 1]
    tail = sorted_r[:k]
    cvar = -sum(tail) / len(tail)

    return max(0.0, var), max(0.0, cvar)


def calculate_parametric_var_cvar(
    mean: float,
    std_dev: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    if not isinstance(std_dev, (int, float)) or not isinstance(confidence, (int, float)):
        raise TypeError("std_dev and confidence must be numeric")

    alpha = 1.0 - confidence
    if std_dev < 0.0 or not 0.0 < alpha < 1.0:
        raise ValueError("std_dev must be non-negative and confidence must be strictly between 0 and 1")

    dist = statistics.NormalDist(mu=0.0, sigma=1.0)
    z_alpha = dist.inv_cdf(alpha)  # Negative quantile, e.g. -1.64485 for 95%

    var = -(mean + z_alpha * std_dev)
    phi_z = dist.pdf(z_alpha)
    cvar = -mean + std_dev * (phi_z / alpha)

    return max(0.0, var), max(0.0, cvar)
