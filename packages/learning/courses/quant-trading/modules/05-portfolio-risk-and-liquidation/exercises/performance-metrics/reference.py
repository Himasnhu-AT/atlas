from __future__ import annotations

import math


def calculate_performance_ratios(
    returns: list[float],
    rf_per_period: float = 0.0,
    mar: float = 0.0,
    annualized_factor: float = 252.0,
) -> dict[str, float]:
    n = len(returns)
    if n < 2:
        return {"sharpe": 0.0, "sortino": 0.0}

    excess_returns = [r - rf_per_period for r in returns]
    mean_excess = sum(excess_returns) / n

    # Population standard deviation of excess returns.
    var = sum((excess_return - mean_excess) ** 2 for excess_return in excess_returns) / n
    std_dev = math.sqrt(var) if var > 0 else 0.0

    # Downside semi-deviation of excess returns below MAR.
    downside_sq = sum(min(0.0, r - rf_per_period - mar) ** 2 for r in returns) / n
    downside_dev = math.sqrt(downside_sq)

    ann_mult = math.sqrt(annualized_factor)
    sharpe = (mean_excess / std_dev * ann_mult) if std_dev > 1e-12 else 0.0
    sortino = ((mean_excess - mar) / downside_dev * ann_mult) if downside_dev > 1e-12 else 0.0

    return {"sharpe": sharpe, "sortino": sortino}
