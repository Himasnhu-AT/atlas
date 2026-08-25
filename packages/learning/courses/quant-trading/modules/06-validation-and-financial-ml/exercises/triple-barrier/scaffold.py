from __future__ import annotations


def apply_triple_barrier(
    prices: list[float],
    pt_pct: float = 0.02,
    sl_pct: float = 0.02,
    max_holding_period: int = 5,
) -> list[int]:
    """
    Apply triple-barrier labeling to a price series.

    prices: list of asset prices
    pt_pct: profit-take fraction above entry (> 0)
    sl_pct: stop-loss fraction below entry (> 0)
    max_holding_period: maximum steps before vertical barrier expiration (> 0)

    Returns a list of integer labels (+1 for upper hit, -1 for lower hit, 0 for vertical timeout).
    """
    raise NotImplementedError
