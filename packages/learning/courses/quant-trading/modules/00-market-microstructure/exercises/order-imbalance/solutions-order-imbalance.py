from __future__ import annotations


def calculate_effective_spread(trade_price: float, mid_price: float) -> float:
    return 2.0 * abs(trade_price - mid_price)


def calculate_order_imbalance(
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    depth: int = 1,
) -> float:
    if not bids or not asks or depth <= 0:
        return 0.0

    k = min(depth, len(bids), len(asks))
    if k == 0:
        return 0.0

    num = 0.0
    den = 0.0

    for i in range(k):
        weight = (k - i) / k
        bid_qty = bids[i][1]
        ask_qty = asks[i][1]
        num += weight * (bid_qty - ask_qty)
        den += weight * (bid_qty + ask_qty)

    if den == 0.0:
        return 0.0

    return max(-1.0, min(1.0, num / den))
