from __future__ import annotations


def construct_dollar_neutral_weights(
    scores: dict[str, float],
    top_n: int = 2,
) -> dict[str, float]:
    n = len(scores)
    if top_n <= 0 or (2 * top_n) > n:
        raise ValueError(
            f"top_n={top_n} is invalid for universe of size {n} (requires 2*top_n <= n)"
        )

    # Sort descending by score
    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    long_weight = 0.5 / top_n
    short_weight = -0.5 / top_n

    weights: dict[str, float] = {k: 0.0 for k in scores}

    for i in range(top_n):
        top_sym = sorted_items[i][0]
        bot_sym = sorted_items[n - 1 - i][0]
        weights[top_sym] = long_weight
        weights[bot_sym] = short_weight

    return weights
