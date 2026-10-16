"""app/forecast/models.py – statsforecast wrapper.

Wraps TSB, CrostonOptimized, and WindowAverage.
Chooses best model per SKU by lowest rolling-origin WAPE.
Falls back to WindowAverage for SKUs with < 8 weeks of history.
"""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from app.forecast.metrics import rmse

logger = logging.getLogger(__name__)

# statsforecast 1.7 warns on every forecast() call that the id will become a column. Opt in now;
# the code below picks the prediction column by name, so it works with either layout.
os.environ.setdefault("NIXTLA_ID_AS_COL", "1")

MIN_HISTORY_WEEKS = 8
WINDOW_SIZE = 4
# Weeks of one-step errors behind sigma. The backtest (python -m app.eval.backtest) showed 8 weeks
# gives an estimate that swings about 3x more between weeks than 26 weeks (CV 0.17 vs 0.06), with
# no gain in stockouts or safety stock from the shorter window.
SIGMA_LOOKBACK_WEEKS = 26


@functools.lru_cache(maxsize=1)
def _try_import_statsforecast():
    try:
        from statsforecast import StatsForecast
        from statsforecast.models import (
            TSB,
            CrostonOptimized,
            WindowAverage,
        )

        return StatsForecast, TSB, CrostonOptimized, WindowAverage
    except ImportError as exc:
        # Never stay silent: without statsforecast every SKU quietly gets the moving average.
        logger.warning(
            "statsforecast is unavailable (%s); using the moving-average fallback for all SKUs", exc
        )
        return None, None, None, None


def make_model(name: str):
    """Model instance for a name forecast_sku reports: TSB, CrostonOptimized or WindowAverage."""
    _, TSB, CrostonOptimized, WindowAverage = _try_import_statsforecast()
    if name == "TSB":
        return TSB(alpha_d=0.2, alpha_p=0.2)
    if name == "CrostonOptimized":
        return CrostonOptimized()
    return WindowAverage(window_size=WINDOW_SIZE)


def predict(name: str, values: np.ndarray, index: pd.PeriodIndex, h: int) -> np.ndarray:
    """Fit the named model on `values` (weekly, aligned with `index`) and forecast h weeks."""
    StatsForecast, *_ = _try_import_statsforecast()
    df = pd.DataFrame(
        {
            "unique_id": ["sku"] * len(values),
            "ds": [p.to_timestamp() for p in index[: len(values)]],
            "y": values,
        }
    )
    fc = StatsForecast(models=[make_model(name)], freq="W", n_jobs=1).forecast(df=df, h=h)
    col = [c for c in fc.columns if c not in ("unique_id", "ds")][0]
    return fc[col].values.astype(float)


def one_step_forecasts(
    name: str, values: np.ndarray, index: pd.PeriodIndex, start: int, end: int
) -> tuple[list[float], list[float]]:
    """(actuals, predictions) for weeks start..end-1, each predicted from the weeks before it."""
    actuals: list[float] = []
    preds: list[float] = []
    for j in range(start, end):
        try:
            preds.append(float(predict(name, values[:j], index, 1)[0]))
            actuals.append(float(values[j]))
        except Exception as exc:
            logger.debug("one-step forecast failed at week %d: %s", j, exc)
    return actuals, preds


def build_weekly_series(
    transactions: list[dict[str, Any]],
) -> dict[str, pd.Series]:
    """Build zero-filled weekly series per SKU from confirmed transactions.

    Args:
        transactions: list of dicts with keys sku_id, tx_date, qty.

    Returns:
        Dict mapping sku_id -> pd.Series with weekly Periods as index.
    """
    if not transactions:
        return {}

    df = pd.DataFrame(transactions)
    df["tx_date"] = pd.to_datetime(df["tx_date"])
    df["week"] = df["tx_date"].dt.to_period("W")
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)

    # Aggregate qty per SKU per week
    weekly = df.groupby(["sku_id", "week"])["qty"].sum().reset_index()

    # Create full weekly range
    min_week = df["tx_date"].min()
    max_week = df["tx_date"].max()
    full_weeks = pd.period_range(min_week, max_week, freq="W")

    series: dict[str, pd.Series] = {}
    for sku_id, grp in weekly.groupby("sku_id"):
        s = grp.set_index("week")["qty"]
        s = s.reindex(full_weeks, fill_value=0.0)
        series[str(sku_id)] = s

    return series


def forecast_sku(
    series: pd.Series,
    horizon: int = 2,
) -> dict[str, Any]:
    """Forecast demand for a single SKU series.

    Returns:
        dict with keys: forecast (list), model_used, sigma, is_fallback, fallback_reason
        (None, "short_history", "statsforecast_unavailable" or "error"), wape_primary, wape_baseline
    """
    StatsForecast, TSB, CrostonOptimized, WindowAverage = _try_import_statsforecast()

    values = series.values.astype(float)
    n = len(values)

    # Fall back when statsforecast cannot be imported, or the history is too short
    if StatsForecast is None or n < MIN_HISTORY_WEEKS:
        unavailable = StatsForecast is None
        avg = float(np.mean(values[-WINDOW_SIZE:])) if n >= 1 else 0.0
        sigma = float(np.std(values[-WINDOW_SIZE:])) if n >= 2 else 0.0
        return {
            "forecast": [avg] * horizon,
            "model_used": (
                "WindowAverage(statsforecast_unavailable)"
                if unavailable
                else "WindowAverage(fallback)"
            ),
            "sigma": sigma,
            "is_fallback": True,
            "fallback_reason": "statsforecast_unavailable" if unavailable else "short_history",
            "wape_primary": None,
            "wape_baseline": None,
        }

    # Prepare statsforecast input

    # Rolling-origin WAPE (last 4 weeks as hold-out)
    hold_out = min(4, n // 4)
    train_y = values[:-hold_out]
    test_y = values[-hold_out:]

    best_model_name = "WindowAverage"
    best_wape = float("inf")
    baseline_wape = None

    try:
        from statsforecast.models import TSB, CrostonOptimized, WindowAverage

        candidates = [
            ("TSB", TSB(alpha_d=0.2, alpha_p=0.2)),
            ("CrostonOptimized", CrostonOptimized()),
        ]
        baseline = WindowAverage(window_size=WINDOW_SIZE)

        for name, mdl in candidates:
            try:
                df_train = pd.DataFrame(
                    {
                        "unique_id": ["sku"] * len(train_y),
                        "ds": [p.to_timestamp() for p in series.index[: len(train_y)]],
                        "y": train_y,
                    }
                )
                sf = StatsForecast(models=[mdl], freq="W", n_jobs=1)
                fc = sf.forecast(df=df_train, h=hold_out)
                col = [c for c in fc.columns if c not in ("unique_id", "ds")][0]
                pred = fc[col].values
                from app.forecast.metrics import wape as _wape

                w = _wape(test_y, pred)
                if w < best_wape:
                    best_wape = w
                    best_model_name = name
            except Exception as e:
                logger.debug("Model %s failed on rolling-origin: %s", name, e)

        # Baseline WAPE
        try:
            df_train = pd.DataFrame(
                {
                    "unique_id": ["sku"] * len(train_y),
                    "ds": [p.to_timestamp() for p in series.index[: len(train_y)]],
                    "y": train_y,
                }
            )
            sf_base = StatsForecast(models=[baseline], freq="W", n_jobs=1)
            fc_base = sf_base.forecast(df=df_train, h=hold_out)
            col = [c for c in fc_base.columns if c not in ("unique_id", "ds")][0]
            from app.forecast.metrics import wape as _wape

            baseline_wape = _wape(test_y, fc_base[col].values)
        except Exception:
            pass

        # Forecast with full series using best model
        model_map = {"TSB": TSB(alpha_d=0.2, alpha_p=0.2), "CrostonOptimized": CrostonOptimized()}
        chosen = model_map.get(best_model_name, WindowAverage(window_size=WINDOW_SIZE))

        df_full = pd.DataFrame(
            {
                "unique_id": ["sku"] * n,
                "ds": [p.to_timestamp() for p in series.index],
                "y": values,
            }
        )
        sf_final = StatsForecast(models=[chosen], freq="W", n_jobs=1)
        fc_final = sf_final.forecast(df=df_full, h=horizon)
        col = [c for c in fc_final.columns if c not in ("unique_id", "ds")][0]
        forecast_vals = [max(0.0, float(v)) for v in fc_final[col].values]

        # Sigma = RMSE of one-step-ahead forecasts over the last 8 weeks (the model is refit at
        # each step). Safety stock needs the typical size of an error, bias included; the
        # standard deviation of the absolute errors understated it by about half on the seed data.
        actuals, preds = one_step_forecasts(
            best_model_name, values, series.index, max(1, n - SIGMA_LOOKBACK_WEEKS), n
        )
        sigma = rmse(actuals, preds) if len(actuals) >= 2 else float(np.std(values))

        return {
            "forecast": forecast_vals,
            "model_used": best_model_name,
            "sigma": sigma,
            "is_fallback": False,
            "fallback_reason": None,
            "wape_primary": best_wape,
            "wape_baseline": baseline_wape,
        }

    except Exception as exc:
        logger.warning("statsforecast error for sku: %s", exc)
        avg = float(np.mean(values[-WINDOW_SIZE:]))
        sigma = float(np.std(values[-WINDOW_SIZE:])) if n >= 2 else 0.0
        return {
            "forecast": [avg] * horizon,
            "model_used": "WindowAverage(error_fallback)",
            "sigma": sigma,
            "is_fallback": True,
            "fallback_reason": "error",
            "wape_primary": None,
            "wape_baseline": None,
        }
