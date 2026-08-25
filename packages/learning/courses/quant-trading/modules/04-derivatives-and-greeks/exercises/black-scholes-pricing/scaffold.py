from __future__ import annotations

import math


def black_scholes_call(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
) -> float:
    """
    Calculate European call option price using Black-Scholes-Merton.

    spot: Current asset price (S > 0)
    strike: Option strike price (K > 0)
    tau: Time to maturity in years (T - t >= 0)
    r: Annualized risk-free interest rate
    sigma: Annualized implied volatility (sigma >= 0)
    """
    raise NotImplementedError


def black_scholes_put(
    spot: float,
    strike: float,
    tau: float,
    r: float,
    sigma: float,
) -> float:
    """
    Calculate European put option price using Black-Scholes-Merton.
    """
    raise NotImplementedError
