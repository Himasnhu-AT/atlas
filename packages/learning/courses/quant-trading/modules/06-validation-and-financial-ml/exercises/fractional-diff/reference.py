from __future__ import annotations


def fractional_differentiation(
    series: list[float],
    d: float,
    threshold: float = 1e-4,
) -> list[float]:
    if d < 0.0 or d > 1.0:
        raise ValueError("Differencing order d must be in [0.0, 1.0]")
    if not series:
        return []

    if d == 0.0:
        return list(series)

    # Generate binomial weights
    weights: list[float] = [1.0]
    k = 1
    while True:
        w_k = -weights[-1] / k * (d - k + 1.0)
        if abs(w_k) < threshold:
            break
        weights.append(w_k)
        k += 1

    diff_series: list[float] = []
    w_len = len(weights)

    for i in range(len(series)):
        # Dot product with available history
        lookback = min(i + 1, w_len)
        val = sum(weights[k] * series[i - k] for k in range(lookback))
        diff_series.append(val)

    return diff_series
