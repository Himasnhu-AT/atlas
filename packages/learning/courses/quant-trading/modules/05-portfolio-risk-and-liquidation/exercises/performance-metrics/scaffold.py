from __future__ import annotations


def calculate_performance_ratios(
    returns: list[float],
    rf_per_period: float = 0.0,
    mar: float = 0.0,
    annualized_factor: float = 252.0,
) -> dict[str, float]:
    """
    Calculate annualized Sharpe and Sortino ratios from excess returns.

    returns: periodic return series (e.g. daily returns)
    rf_per_period: risk-free rate per period
    mar: minimum acceptable return hurdle measured in the same units as rf_per_period
    annualized_factor: periods per year (default 252 for daily)

    Returns dict {"sharpe": float, "sortino": float}.
    """
    raise NotImplementedError
