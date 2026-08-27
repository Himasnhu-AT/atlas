from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
) -> float:
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike must be strictly positive")

    if tau <= 1e-7:
        return max(0.0, spot - strike)

    if sigma <= 1e-7:
        fwd = spot * math.exp(r * tau)
        return math.exp(-r * tau) * max(0.0, fwd - strike)

    sqrt_tau = math.sqrt(tau)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * tau) / (sigma * sqrt_tau)
    d2 = d1 - sigma * sqrt_tau

    df_r = math.exp(-r * tau)
    return spot * _norm_cdf(d1) - strike * df_r * _norm_cdf(d2)


def black_scholes_put(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
) -> float:
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike must be strictly positive")

    if tau <= 1e-7:
        return max(0.0, strike - spot)

    if sigma <= 1e-7:
        fwd = spot * math.exp(r * tau)
        return math.exp(-r * tau) * max(0.0, strike - fwd)

    sqrt_tau = math.sqrt(tau)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * tau) / (sigma * sqrt_tau)
    d2 = d1 - sigma * sqrt_tau

    df_r = math.exp(-r * tau)
    return strike * df_r * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
