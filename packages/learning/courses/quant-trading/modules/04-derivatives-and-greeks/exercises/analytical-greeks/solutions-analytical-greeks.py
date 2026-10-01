from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(slots=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


def calculate_greeks(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
    is_call: bool = True,
) -> Greeks:
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and strike must be strictly positive")

    if tau <= 1e-7:
        intrinsic = max(0.0, (spot - strike) if is_call else (strike - spot))
        delta = 1.0 if (is_call and spot > strike) else (-1.0 if (not is_call and spot < strike) else 0.0)
        return Greeks(
            price=intrinsic,
            delta=delta,
            gamma=0.0,
            vega=0.0,
            theta=0.0,
            rho=0.0,
        )

    if sigma <= 1e-7:
        fwd = spot * math.exp(r * tau)
        price = math.exp(-r * tau) * max(0.0, (fwd - strike) if is_call else (strike - fwd))
        delta = 1.0 if is_call else -1.0
        return Greeks(price=price, delta=delta, gamma=0.0, vega=0.0, theta=0.0, rho=0.0)

    sqrt_tau = math.sqrt(tau)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * tau) / (sigma * sqrt_tau)
    d2 = d1 - sigma * sqrt_tau

    df_r = math.exp(-r * tau)
    pdf_d1 = _norm_pdf(d1)

    gamma = pdf_d1 / (spot * sigma * sqrt_tau)
    raw_vega = spot * pdf_d1 * sqrt_tau
    vega_1pct = raw_vega / 100.0

    if is_call:
        price = spot * _norm_cdf(d1) - strike * df_r * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta = (
            -(spot * pdf_d1 * sigma) / (2.0 * sqrt_tau) - r * strike * df_r * _norm_cdf(d2)
        ) / 365.0
        rho = (strike * tau * df_r * _norm_cdf(d2)) / 100.0
    else:
        price = strike * df_r * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = -_norm_cdf(-d1)
        theta = (
            -(spot * pdf_d1 * sigma) / (2.0 * sqrt_tau) + r * strike * df_r * _norm_cdf(-d2)
        ) / 365.0
        rho = (-strike * tau * df_r * _norm_cdf(-d2)) / 100.0

    return Greeks(
        price=price,
        delta=delta,
        gamma=gamma,
        vega=vega_1pct,
        theta=theta,
        rho=rho,
    )
