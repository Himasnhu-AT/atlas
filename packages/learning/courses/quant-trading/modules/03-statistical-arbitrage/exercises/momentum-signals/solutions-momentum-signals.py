from __future__ import annotations

import math
import statistics


def calculate_volatility_scaled_momentum(
    prices: list[float],
    lookback: int = 20,
    target_vol: float = 0.15,
    annualized_factor: float = 252.0,
) -> float:
    if len(prices) < lookback + 1 or lookback < 2:
        return 0.0

    recent_prices = prices[-(lookback + 1) :]
    p_start = recent_prices[0]
    p_end = recent_prices[-1]

    if p_start <= 0:
        return 0.0

    mom_return = (p_end - p_start) / p_start
    if mom_return > 0:
        direction = 1.0
    elif mom_return < 0:
        direction = -1.0
    else:
        return 0.0

    returns = [
        (recent_prices[i] - recent_prices[i - 1]) / recent_prices[i - 1]
        for i in range(1, len(recent_prices))
    ]

    daily_vol = statistics.stdev(returns)
    ann_vol = daily_vol * math.sqrt(annualized_factor)

    if ann_vol < 1e-6:
        scale = 1.0
    else:
        scale = target_vol / ann_vol

    return max(-1.0, min(1.0, direction * scale))
