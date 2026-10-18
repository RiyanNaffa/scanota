"""tests/unit/test_forecast_cache.py – The demand forecast is remembered while a SKU's sales stay the same.

/restock used to recompute every SKU's model on every call, so a stock update (which does not
change the sales) or two pages asking at once cost seconds each on a small VM.
"""

from __future__ import annotations

import threading
import time

import pandas as pd
import pytest

from app.forecast import service


@pytest.fixture(autouse=True)
def fresh_cache():
    service._FORECAST_CACHE.clear()
    yield
    service._FORECAST_CACHE.clear()


@pytest.fixture
def calls(monkeypatch):
    """Replace the real model by a counter, so the test is fast and counts the computations."""
    seen: list[int] = []

    def fake(series, horizon=2):
        seen.append(horizon)
        time.sleep(0.02)
        return {
            "forecast": [float(series.values[-1])] * horizon,
            "model_used": "fake",
            "sigma": 1.0,
            "is_fallback": False,
            "fallback_reason": None,
            "wape_primary": 0.5,
            "wape_baseline": 0.6,
        }

    monkeypatch.setattr(service, "forecast_sku", fake)
    return seen


def _series(values):
    return pd.Series(values, index=pd.period_range("2026-01-05", periods=len(values), freq="W"))


def test_same_series_is_computed_once(calls):
    first = service.cached_forecast(_series([1, 2, 3, 4, 5, 6, 7, 8]), horizon=2)
    second = service.cached_forecast(_series([1, 2, 3, 4, 5, 6, 7, 8]), horizon=2)

    assert first == second
    assert len(calls) == 1


def test_a_new_sale_or_another_horizon_is_computed_again(calls):
    base = [1, 2, 3, 4, 5, 6, 7, 8]
    service.cached_forecast(_series(base), horizon=2)
    service.cached_forecast(_series(base + [9]), horizon=2)  # one more week of sales
    service.cached_forecast(_series([2, *base[1:]]), horizon=2)  # one value changed
    service.cached_forecast(_series(base), horizon=4)  # the chart asks for 4 weeks

    assert len(calls) == 4


def test_a_failed_model_run_is_not_remembered(monkeypatch):
    runs = []

    def flaky(series, horizon=2):
        runs.append(1)
        reason = "error" if len(runs) == 1 else None
        return {"forecast": [1.0] * horizon, "fallback_reason": reason, "model_used": "x"}

    monkeypatch.setattr(service, "forecast_sku", flaky)
    series = _series([1, 2, 3, 4, 5, 6, 7, 8])

    assert service.cached_forecast(series, 2)["fallback_reason"] == "error"
    assert service.cached_forecast(series, 2)["fallback_reason"] is None  # tried again
    service.cached_forecast(series, 2)
    assert len(runs) == 2  # and the good result is kept


def test_editing_a_result_does_not_change_what_is_remembered(calls):
    series = _series([1, 2, 3, 4, 5, 6, 7, 8])
    first = service.cached_forecast(series, 2)
    first["forecast"].append(99.0)
    first["model_used"] = "changed"

    again = service.cached_forecast(series, 2)
    assert again["forecast"] == [8.0, 8.0]
    assert again["model_used"] == "fake"


def test_requests_at_the_same_time_share_one_computation(calls):
    series = _series([1, 2, 3, 4, 5, 6, 7, 8])
    results: list[dict] = []

    threads = [
        threading.Thread(target=lambda: results.append(service.cached_forecast(series, 2)))
        for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 6
    assert len(calls) == 1


def test_updating_stock_does_not_recompute_the_forecast(monkeypatch, calls):
    """The reported bug: saving a new stock level made /restock recompute every model."""
    sales = [
        {"sku_id": "TNK001", "tx_date": f"2026-0{m}-{d:02d}", "qty": float(m + d % 3)}
        for m in range(1, 5)
        for d in (3, 10, 17, 24)
    ]
    stock = {"value": 40.0}

    def products(_db):
        return [
            {
                "sku_id": "TNK001",
                "name": "Isotank 500L",
                "category": "Tangki Air",
                "unit": "pcs",
                "current_stock": stock["value"],
                "lead_time_days": 3,
            }
        ]

    monkeypatch.setattr(service, "get_products", products)
    monkeypatch.setattr(service, "get_confirmed_item_sales", lambda _db: sales)

    before = service.build_restock_list(None)
    stock["value"] = 2.0
    after = service.build_restock_list(None)

    assert len(calls) == 1  # the model ran once, for the first list
    assert before[0]["current_stock"] == 40.0
    assert after[0]["current_stock"] == 2.0
    assert after[0]["forecast_next_2_weeks"] == before[0]["forecast_next_2_weeks"]
    assert after[0]["action"] != before[0]["action"]  # the stock-dependent part did change
