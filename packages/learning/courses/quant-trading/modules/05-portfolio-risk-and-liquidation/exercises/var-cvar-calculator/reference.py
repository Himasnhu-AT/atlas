from __future__ import annotations

import math
import statistics


def calculate_historical_var_cvar(
    returns: list[float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    if not returns:
        return 0.0, 0.0

    sorted_r = sorted(returns)
    n = len(sorted_r)
    alpha = 1.0 - confidence
    k = max(1, int(math.floor(alpha * n)))

    var = -sorted_r[k - 1]
    tail = sorted_r[:k]
    cvar = -sum(tail) / len(tail)

    return max(0.0, var), max(0.0, cvar)


def calculate_parametric_var_cvar(
    mean: float,
    std_dev: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    alpha = 1.0 - confidence
    dist = statistics.NormalDist(mu=0.0, sigma=1.0)
    z_alpha = dist.inv_cdf(alpha)  # Negative quantile, e.g. -1.64485 for 95%

    var = -(mean + z_alpha * std_dev)
    phi_z = dist.pdf(z_alpha)
    cvar = -mean + std_dev * (phi_z / alpha)

    return max(0.0, var), max(0.0, cvar)
