from __future__ import annotations

import math


def calculate_spread_zscore(
    y: list[float],
    x: list[float],
) -> dict[str, float | list[float]]:
    n = len(y)
    if n != len(x):
        raise ValueError("Series y and x must have identical length")
    if n < 2:
        raise ValueError("Series length must be at least 2")

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xx = sum(xi * xi for xi in x)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))

    denom = n * sum_xx - sum_x * sum_x
    if math.isclose(denom, 0.0, abs_tol=1e-12):
        raise ZeroDivisionError("Zero variance in independent variable x")

    beta = (n * sum_xy - sum_x * sum_y) / denom
    alpha = (sum_y - beta * sum_x) / n

    residuals = [yi - (alpha + beta * xi) for xi, yi in zip(x, y)]
    mean_res = sum(residuals) / n
    var_res = sum((r - mean_res) ** 2 for r in residuals) / (n - 1)
    std_res = math.sqrt(var_res)

    z_score = (residuals[-1] - mean_res) / std_res if std_res > 1e-12 else 0.0

    return {
        "beta": beta,
        "alpha": alpha,
        "residuals": residuals,
        "z_score": z_score,
    }
