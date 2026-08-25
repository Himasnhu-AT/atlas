from __future__ import annotations


def generate_pairs_signals(
    z_score: float,
    current_position: int,
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
    stop_loss: float = 3.5,
) -> int:
    """
    State machine for cointegrated pairs trading.

    current_position: +1 (Long Spread), -1 (Short Spread), 0 (Flat).
    Returns target position (+1, -1, or 0).
    """
    raise NotImplementedError
