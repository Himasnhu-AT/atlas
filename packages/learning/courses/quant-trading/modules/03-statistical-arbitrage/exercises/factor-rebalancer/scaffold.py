from __future__ import annotations


def construct_dollar_neutral_weights(
    scores: dict[str, float],
    top_n: int = 2,
) -> dict[str, float]:
    """
    Construct dollar-neutral long/short weights from cross-sectional factor scores.

    Top `top_n` assets are weighted equally to sum to +0.5.
    Bottom `top_n` assets are weighted equally to sum to -0.5.
    All other assets receive weight 0.0.

    Raises ValueError if 2 * top_n > len(scores) or top_n <= 0.
    """
    raise NotImplementedError
