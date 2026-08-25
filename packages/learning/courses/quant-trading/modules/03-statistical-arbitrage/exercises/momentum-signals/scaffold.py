from __future__ import annotations


def calculate_volatility_scaled_momentum(
    prices: list[float],
    lookback: int = 20,
    target_vol: float = 0.15,
    annualized_factor: float = 252.0,
) -> float:
    """
    Compute directional momentum scaled by annualized realized volatility.

    Returns target weight in [-1.0, 1.0].
    Returns 0.0 if len(prices) < lookback + 1.
    """
    raise NotImplementedError
