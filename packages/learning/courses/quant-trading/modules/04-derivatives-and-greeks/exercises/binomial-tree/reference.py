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
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike must be strictly positive")
    if tau <= 0 or steps <= 0:
        return max(0.0, (spot - strike) if is_call else (strike - spot))

    dt = tau / steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    disc = math.exp(-r * dt)
    p = (math.exp(r * dt) - d) / (u - d)

    # Initialize terminal payoff array at step N
    values = [0.0] * (steps + 1)
    for j in range(steps + 1):
        st = spot * (u**j) * (d ** (steps - j))
        values[j] = max(0.0, (st - strike) if is_call else (strike - st))

    # Backward induction from step N-1 down to 0
    for i in range(steps - 1, -1, -1):
        for j in range(i + 1):
            continuation = disc * (p * values[j + 1] + (1.0 - p) * values[j])
            if is_american:
                st = spot * (u**j) * (d ** (i - j))
                intrinsic = max(0.0, (st - strike) if is_call else (strike - st))
                values[j] = max(continuation, intrinsic)
            else:
                values[j] = continuation

    return values[0]
