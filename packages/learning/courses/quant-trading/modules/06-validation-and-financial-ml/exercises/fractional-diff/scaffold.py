from __future__ import annotations


def fractional_differentiation(
    series: list[float],
    d: float,
    threshold: float = 1e-4,
) -> list[float]:
    """
    Compute fractionally differentiated series using fixed-width window weights.

    series: list of price observations
    d: fractional differencing order (0.0 <= d <= 1.0)
    threshold: minimum absolute weight cutoff for finite memory window

    Returns a list of fractionally differentiated values of identical length.
    """
    raise NotImplementedError
