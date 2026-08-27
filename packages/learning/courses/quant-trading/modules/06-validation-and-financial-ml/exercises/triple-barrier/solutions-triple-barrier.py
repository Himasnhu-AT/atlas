from __future__ import annotations


def apply_triple_barrier(
    prices: list[float],
    pt_pct: float = 0.02,
    sl_pct: float = 0.02,
    max_holding_period: int = 5,
) -> list[int]:
    if pt_pct <= 0 or sl_pct <= 0 or max_holding_period <= 0:
        raise ValueError("Barriers and max_holding_period must be strictly positive")

    n = len(prices)
    labels: list[int] = []

    for i in range(n):
        entry_price = prices[i]
        upper = entry_price * (1.0 + pt_pct)
        lower = entry_price * (1.0 - sl_pct)
        label = 0

        # Scan forward up to max_holding_period
        for h in range(1, max_holding_period + 1):
            j = i + h
            if j >= n:
                break
            p = prices[j]
            if p >= upper:
                label = 1
                break
            elif p <= lower:
                label = -1
                break

        labels.append(label)

    return labels
