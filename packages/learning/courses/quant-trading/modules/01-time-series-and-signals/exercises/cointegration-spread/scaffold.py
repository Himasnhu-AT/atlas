from __future__ import annotations


def calculate_spread_zscore(
    y: list[float],
    x: list[float],
) -> dict[str, float | list[float]]:
    """
    Compute OLS regression: Y = alpha + beta * X + e.

    Returns a dict with:
        "beta": OLS slope (hedge ratio)
        "alpha": OLS intercept
        "residuals": list of spread residuals e_t
        "z_score": normalized z-score of the most recent residual e[-1]

    Raises ValueError if series lengths do not match or length < 2.
    Raises ZeroDivisionError if variance of x is zero.
    """
    raise NotImplementedError
