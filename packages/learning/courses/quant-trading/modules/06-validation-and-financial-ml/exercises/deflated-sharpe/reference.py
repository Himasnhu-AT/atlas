from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def calculate_deflated_sharpe(
    sharpe: float,
    num_trials: int = 1,
    sample_length: int = 252,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> dict[str, float]:
    if num_trials < 1 or sample_length < 3:
        raise ValueError("num_trials must be >= 1 and sample_length must be >= 3")

    # Expected maximum Sharpe under standard normal trials
    if num_trials == 1:
        sr_star = 0.0
    else:
        gamma_const = 0.5772156649  # Euler-Mascheroni constant
        log_n = math.log(num_trials)
        sqrt_2log_n = math.sqrt(2.0 * log_n)
        sr_star = sqrt_2log_n + (gamma_const / sqrt_2log_n)

    # Standard error of Sharpe ratio
    variance_term = (
        1.0 - skewness * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe * sharpe)
    )
    se_sr = math.sqrt(max(1e-12, variance_term) / (sample_length - 1))

    z_score = (sharpe - sr_star) / se_sr
    dsr = _norm_cdf(z_score)

    return {
        "expected_max_sharpe": sr_star,
        "dsr": dsr,
    }
