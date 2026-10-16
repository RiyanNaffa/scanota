"""tests/unit/test_forecast_models.py – statsforecast wrapper: fallbacks must be visible."""
from __future__ import annotations

import importlib.util
import logging
import sys

import numpy as np
import pandas as pd
import pytest

from app.forecast import models
from app.forecast.metrics import rmse
from app.forecast.models import forecast_sku
from app.forecast.service import data_quality_label


def _series(values) -> pd.Series:
    index = pd.period_range("2025-01-06", periods=len(values), freq="W")
    return pd.Series(np.asarray(values, dtype=float), index=index)


@pytest.fixture(autouse=True)
def _fresh_import_cache():
    models._try_import_statsforecast.cache_clear()
    yield
    models._try_import_statsforecast.cache_clear()


def test_missing_statsforecast_warns_once_and_is_labelled(monkeypatch, caplog):
    """Regression: a broken install used to fall back silently, labelled as short history."""
    monkeypatch.setitem(sys.modules, "statsforecast", None)  # makes the import raise ImportError
    series = _series([3, 0, 2, 0, 0, 4, 1, 0, 2, 3, 0, 1] * 3)

    with caplog.at_level(logging.WARNING, logger="app.forecast.models"):
        first = forecast_sku(series)
        forecast_sku(series)

    assert first["model_used"] == "WindowAverage(statsforecast_unavailable)"
    assert first["fallback_reason"] == "statsforecast_unavailable"
    assert first["is_fallback"] is True
    warnings = [r for r in caplog.records if "statsforecast is unavailable" in r.getMessage()]
    assert len(warnings) == 1  # cached: one line per process, not one per SKU


def test_short_history_is_a_different_fallback(monkeypatch):
    monkeypatch.setattr(models, "_try_import_statsforecast", lambda: (object(), None, None, None))

    result = forecast_sku(_series([1, 2, 3, 4, 5]))

    assert result["fallback_reason"] == "short_history"
    assert result["model_used"] == "WindowAverage(fallback)"
    assert result["forecast"] == [pytest.approx(3.5)] * 2


@pytest.mark.parametrize(
    ("reason", "label"),
    [
        (None, "ok"),
        ("short_history", "insufficient_history"),
        ("no_data", "insufficient_history"),
        ("statsforecast_unavailable", "model_unavailable"),
        ("error", "model_unavailable"),
    ],
)
def test_data_quality_label(reason, label):
    assert data_quality_label({"fallback_reason": reason}) == label


def test_real_models_run_when_statsforecast_is_installed():
    """Runs in CI and in the Docker image; skipped only when the package is truly absent.

    An installed but broken statsforecast (for example the pyarrow/NumPy mismatch) must FAIL
    here, so the import is done outside any skip logic.
    """
    if importlib.util.find_spec("statsforecast") is None:
        pytest.skip("statsforecast is not installed in this environment")
    import statsforecast  # noqa: F401

    rng = np.random.default_rng(42)
    series = _series(rng.poisson(0.8, 40) * 3)

    result = forecast_sku(series, horizon=2)

    assert result["fallback_reason"] is None
    assert result["is_fallback"] is False
    assert result["model_used"] in {"TSB", "CrostonOptimized"}
    assert len(result["forecast"]) == 2
    assert all(v >= 0 for v in result["forecast"])
    assert result["sigma"] >= 0


def test_sigma_is_the_rmse_of_one_step_errors():
    """Regression: sigma used to be std(abs(error)), about half of the real error spread."""
    if importlib.util.find_spec("statsforecast") is None:
        pytest.skip("statsforecast is not installed in this environment")
    from statsforecast import StatsForecast
    from statsforecast.models import TSB, CrostonOptimized

    rng = np.random.default_rng(7)
    series = _series(rng.poisson(1.2, 45) * 2)

    result = forecast_sku(series, horizon=2)

    make = (lambda: TSB(alpha_d=0.2, alpha_p=0.2)) if result["model_used"] == "TSB" else CrostonOptimized
    values = series.values.astype(float)
    actuals, preds = [], []
    for j in range(len(values) - 8, len(values)):
        df = pd.DataFrame(
            {"unique_id": "sku", "ds": [p.to_timestamp() for p in series.index[:j]], "y": values[:j]}
        )
        fc = StatsForecast(models=[make()], freq="W", n_jobs=1).forecast(df=df, h=1)
        preds.append(float(fc.iloc[:, -1].values[0]))
        actuals.append(values[j])

    assert result["sigma"] == pytest.approx(rmse(actuals, preds))
    assert result["sigma"] > float(np.std(np.abs(np.subtract(preds, actuals))))
