from __future__ import annotations


def calculate_historical_var_cvar(
    returns: list[float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Calculate historical Value at Risk and Expected Shortfall (CVaR).
    Returns (var, cvar) as positive loss values.
    """
    raise NotImplementedError


def calculate_parametric_var_cvar(
    mean: float,
    std_dev: float,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Calculate Gaussian parametric Value at Risk and Expected Shortfall (CVaR).
    Returns (var, cvar) as positive loss values.
    """
    raise NotImplementedError
