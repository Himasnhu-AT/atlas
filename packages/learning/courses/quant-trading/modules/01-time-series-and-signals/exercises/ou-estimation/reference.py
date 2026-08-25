from __future__ import annotations

import math


def estimate_ou_parameters(series: list[float], dt: float = 1.0) -> dict[str, float]:
    if len(series) < 3:
        raise ValueError("Series must contain at least 3 points")
    if dt <= 0:
        raise ValueError("dt must be strictly positive")

    x = series[:-1]
    y = series[1:]
    n = len(x)

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(xi * xi for xi in x)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))

    denom = n * sum_xx - sum_x * sum_x
    if math.isclose(denom, 0.0, abs_tol=1e-12):
        raise ValueError("Variance of x is zero")

    b = (n * sum_xy - sum_x * sum_y) / denom
    a = (sum_y - b * sum_x) / n

    if b <= 0.0 or b >= 1.0:
        raise ValueError(f"Series is not mean-reverting (AR(1) slope b={b:.4f} not in (0, 1))")

    theta = -math.log(b) / dt
    mu = a / (1.0 - b)

    residuals = [yi - (a + b * xi) for xi, yi in zip(x, y)]
    var_eps = sum(r * r for r in residuals) / max(1, n - 2)

    sigma_sq = (var_eps * 2.0 * theta) / (1.0 - b * b)
    sigma = math.sqrt(max(0.0, sigma_sq))
    half_life = math.log(2.0) / theta

    return {
        "theta": theta,
        "mu": mu,
        "sigma": sigma,
        "half_life": half_life,
    }
