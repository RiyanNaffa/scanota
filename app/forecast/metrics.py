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


def rmse(actual: list[float] | np.ndarray, forecast: list[float] | np.ndarray) -> float:
    """Root mean squared error: the typical size of a forecast error, bias included.

    This is the sigma that safety stock needs. np.std(abs(error)) is not: it measures how much
    the error sizes vary, so errors of +3, -3, +3, -3 give 0 instead of 3.
    Returns 0.0 for empty input.
    """
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if a.size == 0:
        return 0.0
    return float(np.sqrt(np.mean((f - a) ** 2)))
