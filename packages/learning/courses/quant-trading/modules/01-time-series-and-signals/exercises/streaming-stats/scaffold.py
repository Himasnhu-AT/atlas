from __future__ import annotations

from collections import deque
import math


class StreamingEMA:
    """
    Online exponential moving average with initialization warmup.
    """

    def __init__(self, window: int) -> None:
        self.window = window
        self.alpha = 2.0 / (window + 1.0)
        self.value: float | None = None

    def update(self, price: float) -> float:
        """
        Ingest price and return the current EMA.
        For the first `window` observations, returns the running arithmetic mean.
        Thereafter, applies exponential smoothing.
        """
        raise NotImplementedError


class RollingVariance:
    """
    Sliding window sample variance and volatility tracker.
    """

    def __init__(self, window: int, annualized_factor: float = 252.0) -> None:
        self.window = window
        self.annualized_factor = annualized_factor

    def update(self, x: float) -> tuple[float, float]:
        """
        Ingest new value x.
        Returns a tuple of (sample_variance, annualized_volatility).
        If fewer than 2 items are in the window, returns (0.0, 0.0).
        """
        raise NotImplementedError
