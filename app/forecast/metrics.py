"""app/forecast/metrics.py – Forecast accuracy metrics."""
from __future__ import annotations

import numpy as np


def wape(actual: list[float] | np.ndarray, forecast: list[float] | np.ndarray) -> float:
    """Weighted Absolute Percentage Error.

    wape = sum|a - f| / sum(a)
    Returns 0.0 when sum(actual) == 0 (no sales to measure against).
    """
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    denom = np.sum(a)
    if denom == 0:
        return 0.0
    return float(np.sum(np.abs(a - f)) / denom)


def bias(actual: list[float] | np.ndarray, forecast: list[float] | np.ndarray) -> float:
    """Mean signed error (positive = over-forecast)."""
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if len(a) == 0:
        return 0.0
    return float(np.mean(f - a))
