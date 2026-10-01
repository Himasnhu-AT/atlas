from __future__ import annotations


def generate_pairs_signals(
    z_score: float,
    current_position: int,
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
    stop_loss: float = 3.5,
) -> int:
    if current_position == 0:
        if z_score <= -entry_threshold:
            return 1
        elif z_score >= entry_threshold:
            return -1
        return 0

    elif current_position == 1:
        if z_score <= -stop_loss or z_score >= -exit_threshold:
            return 0
        return 1

    elif current_position == -1:
        if z_score >= stop_loss or z_score <= exit_threshold:
            return 0
        return -1

    return 0
