from __future__ import annotations

import math


def price_binomial_tree(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
    steps: int = 100,
    is_call: bool = True,
    is_american: bool = True,
) -> float:
    """
    Price European or American options via Cox-Ross-Rubinstein binomial tree in O(N) space.
    """
    raise NotImplementedError
