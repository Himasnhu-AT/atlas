from __future__ import annotations


def calculate_drawdown_metrics(equity_curve: list[float]) -> dict[str, float | int]:
    if not equity_curve:
        return {"max_drawdown": 0.0, "max_duration": 0, "current_drawdown": 0.0}

    peak = equity_curve[0]
    underwater_duration = 0
    max_dd = 0.0
    max_duration = 0

    for i, val in enumerate(equity_curve):
        if val >= peak:
            peak = val
            underwater_duration = 0
        else:
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
            underwater_duration += 1

        if underwater_duration > max_duration:
            max_duration = underwater_duration

    current_dd = (peak - equity_curve[-1]) / peak if peak > 0 else 0.0

    return {
        "max_drawdown": max_dd,
        "max_duration": max_duration,
        "current_drawdown": current_dd,
    }
