from __future__ import annotations

import math
import statistics


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

    # Expected maximum Sharpe under independent standard-normal trials.
    if num_trials == 1:
        sr_star = 0.0
    else:
        gamma_const = 0.5772156649  # Euler-Mascheroni constant
        normal = statistics.NormalDist(mu=0.0, sigma=1.0)
        upper_tail_1_over_n = normal.inv_cdf(1.0 - 1.0 / num_trials)
        upper_tail_1_over_ne = normal.inv_cdf(1.0 - 1.0 / (num_trials * math.e))
        sr_star = (1.0 - gamma_const) * upper_tail_1_over_n + gamma_const * upper_tail_1_over_ne

    # Standard error of Sharpe ratio
    variance_term = (
        1.0 - skewness * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe * sharpe)
    )
    se_sr = math.sqrt(max(1e-12, variance_term) / (sample_length - 1))

    z_score = (sharpe - sr_star) / se_sr
    dsr = _norm_cdf(z_score) if z_score < 0 else 1.0

    return {
        "expected_max_sharpe": sr_star,
        "dsr": dsr,
    }
