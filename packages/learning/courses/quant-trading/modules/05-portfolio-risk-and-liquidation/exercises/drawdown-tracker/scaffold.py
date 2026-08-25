from __future__ import annotations


def calculate_drawdown_metrics(equity_curve: list[float]) -> dict[str, float | int]:
    """
    Calculate drawdown depth and duration metrics from an equity curve.

    Returns a dict with:
        "max_drawdown": maximum peak-to-trough fractional decline (>= 0.0)
        "max_duration": maximum consecutive steps spent below high-water mark (int)
        "current_drawdown": fractional decline of the final equity point from all-time peak
    """
    raise NotImplementedError
