from __future__ import annotations


def calculate_kelly_fraction(
    win_rate: float,
    win_loss_ratio: float,
    fraction_multiplier: float = 0.5,
    max_cap: float = 0.5,
) -> float:
    """
    Calculate fractional Kelly position sizing.

    win_rate (p): Probability of winning trade in (0, 1).
    win_loss_ratio (b): Average win dollar amount / average loss dollar amount (> 0).
    fraction_multiplier: Scaling factor (e.g. 0.5 for Half-Kelly).
    max_cap: Hard ceiling on position size in [0, 1].

    Returns optimal allocation fraction clamped to [0.0, max_cap].
    """
    raise NotImplementedError
