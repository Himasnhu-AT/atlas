from __future__ import annotations


def calculate_kelly_fraction(
    win_rate: float,
    win_loss_ratio: float,
    fraction_multiplier: float = 0.5,
    max_cap: float = 0.5,
) -> float:
    if win_rate <= 0.0 or win_rate >= 1.0 or win_loss_ratio <= 0.0:
        return 0.0

    p = win_rate
    q = 1.0 - p
    b = win_loss_ratio

    full_kelly = (p * (b + 1.0) - 1.0) / b
    if full_kelly <= 0.0:
        return 0.0

    fractional = full_kelly * fraction_multiplier
    return max(0.0, min(max_cap, fractional))
