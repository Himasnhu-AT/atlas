from __future__ import annotations

from collections import deque
import math


class StreamingEMA:
    def __init__(self, window: int) -> None:
        if window < 1:
            raise ValueError("Window must be >= 1")
        self.window = window
        self.alpha = 2.0 / (window + 1.0)
        self.value: float | None = None
        self._count = 0
        self._sum = 0.0

    def update(self, price: float) -> float:
        self._count += 1
        if self._count < self.window:
            self._sum += price
            self.value = self._sum / self._count
        elif self._count == self.window:
            self._sum += price
            self.value = self._sum / self.window
        else:
            self.value = self.alpha * price + (1.0 - self.alpha) * self.value
        return self.value


class RollingVariance:
    def __init__(self, window: int, annualized_factor: float = 252.0) -> None:
        if window < 2:
            raise ValueError("Window must be >= 2")
        self.window = window
        self.annualized_factor = annualized_factor
        self.queue: deque[float] = deque()
        self._sum = 0.0
        self._sum_sq = 0.0

    def update(self, x: float) -> tuple[float, float]:
        self.queue.append(x)
        self._sum += x
        self._sum_sq += x * x

        if len(self.queue) > self.window:
            old = self.queue.popleft()
            self._sum -= old
            self._sum_sq -= old * old

        n = len(self.queue)
        if n < 2:
            return 0.0, 0.0

        mean = self._sum / n
        variance = max(0.0, (self._sum_sq - n * mean * mean) / (n - 1))
        annualized_vol = math.sqrt(variance * self.annualized_factor)
        return variance, annualized_vol
