from __future__ import annotations


def calculate_effective_spread(trade_price: float, mid_price: float) -> float:
    """
    Calculate effective spread: 2 * |trade_price - mid_price|.
    """
    raise NotImplementedError


def calculate_order_imbalance(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    depth: int = 1,
) -> float:
    """
    Compute multi-level depth-weighted order book imbalance in [-1.0, 1.0].

    bids: list of (price, quantity) sorted descending by price.
    asks: list of (price, quantity) sorted ascending by price.
    depth: number of top price levels to consider.
    Weight for level i (0-indexed) is (k - i) / k, where k = min(depth, len(bids), len(asks)).
    Returns 0.0 if total volume is 0 or either side has no levels.
    """
    raise NotImplementedError
