"""tests/unit/test_backtest.py – Scoring helpers of the forecast backtest, plus a small end-to-end run."""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from app.eval import backtest
from app.eval.backtest import (
    format_report,
    holdout_check,
    lead_time_demand,
    run_backtest,
    sigma_stability,
    stockout_stats,
    suggest_z,
    tier_z,
    z_for_target,
)


def test_stockout_stats():
    stats = stockout_stats([5, 5, 5, 5], [3, 5, 6, 10])

    assert stats["stockout_rate"] == pytest.approx(0.5)  # 6 and 10 exceed 5; 5 does not
    assert stats["unmet_pct"] == pytest.approx((1 + 5) / 24)
    assert stats["avg_rop"] == 5
    assert stats["n"] == 4


def test_stockout_stats_empty_and_zero_demand():
    assert stockout_stats([], [])["n"] == 0
    assert stockout_stats([2, 2], [0, 0])["unmet_pct"] == 0.0


def test_lead_time_demand_counts_the_lead_days_from_the_start_day():
    days = pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09"])
    daily = pd.Series([3.0, 2.0, 4.0, 10.0], index=days)

    assert lead_time_demand(daily, pd.Timestamp("2025-01-06"), 3) == 9.0  # Jan 9 is day 4
    assert lead_time_demand(daily, pd.Timestamp("2025-01-07"), 1) == 2.0
    assert lead_time_demand(daily, pd.Timestamp("2025-02-01"), 3) == 0.0


def test_z_for_target_hits_the_target_rate():
    realised = list(np.linspace(0, 9.9, 100))
    z = z_for_target([0.0] * 100, [1.0] * 100, realised, target=0.05)

    assert z == pytest.approx(9.5)
    assert np.mean(np.array(realised) > z) <= 0.05


def test_z_for_target_is_infinite_when_zero_sigma_cannot_cover_demand():
    z = z_for_target([1.0] * 10, [0.0] * 10, [5.0] * 5 + [0.0] * 5, target=0.05)
    assert z == float("inf")


def test_sigma_stability():
    assert sigma_stability({"a": [2.0, 2.0, 2.0]}) == 0.0
    assert sigma_stability({"a": [1.0, 3.0]}) == pytest.approx(0.5)  # std 1 / mean 2
    assert sigma_stability({"a": [1.0]}) == 0.0


def _rows(n_weeks: int = 70) -> tuple[list[dict], dict[str, int]]:
    rng = np.random.default_rng(3)
    start = pd.Timestamp("2025-01-06")  # a Monday
    rows = []
    for sku in ("A", "B", "C"):
        for w in range(n_weeks):
            if rng.random() < 0.3:
                continue
            day = start + pd.Timedelta(weeks=w, days=int(rng.integers(0, 7)))
            rows.append(
                {"sku_id": sku, "tx_date": str(day.date()), "qty": float(rng.integers(1, 8))}
            )
    return rows, {"A": 2, "B": 3, "C": 5}


def test_end_to_end_when_statsforecast_is_installed():
    if importlib.util.find_spec("statsforecast") is None:
        pytest.skip("statsforecast is not installed in this environment")
    rows, lead_days = _rows()

    result = run_backtest(rows, lead_days, origins=3)

    assert result["skus"] == 3
    for method, per in result["methods"].items():
        assert per["all"]["n"] == 9, method  # 3 SKUs x 3 origins
        assert 0.0 <= per["all"]["stockout_rate"] <= 1.0
    assert {"baseline_ma4", "old_abs_std8", "rmse8", "rmse26"} <= set(result["methods"])
    assert result["max_sigma_mismatch"] < 1e-9  # backtest and forecast_sku agree on sigma
    text = format_report(result)
    assert "Calibration and stability" in text and "Stockout rate by lead time" in text


def test_backtest_refuses_to_run_without_the_real_models(monkeypatch):
    monkeypatch.setattr(backtest.models, "_try_import_statsforecast", lambda: (None,) * 4)
    with pytest.raises(RuntimeError, match="statsforecast"):
        run_backtest([{"sku_id": "A", "tx_date": "2025-01-06", "qty": 1.0}], {})


def _target(category: str) -> float:
    return 0.10 if category == "Spoils" else 0.05


def _case(
    category: str, T: int, realised: float, base_lt: float = 10.0, scale: float = 1.0
) -> dict:
    return {"category": category, "T": T, "realised": realised, "base_lt": base_lt, "scale": scale}


def test_suggest_z_pulls_a_small_sample_toward_the_pooled_value():
    calibration = {
        "Big": {"n": 1500, "z_for_5pct": 3.0, "z_for_10pct": 2.0},
        "Tiny": {"n": 15, "z_for_5pct": 3.0, "z_for_10pct": 2.0},
    }
    z = suggest_z(calibration, {0.05: 2.0, 0.10: 1.5}, _target, k=150)

    assert z["Big"] == pytest.approx(2.9, abs=0.05)  # 1500 cases: nearly its own 3.0
    assert z["Tiny"] == pytest.approx(2.1, abs=0.05)  # 15 cases: nearly the pooled 2.0


def test_suggest_z_uses_the_looser_target_for_goods_that_spoil():
    calibration = {"Spoils": {"n": 150, "z_for_5pct": 3.0, "z_for_10pct": 2.0}}
    assert (
        suggest_z(calibration, {0.05: 2.5, 0.10: 1.5}, _target, k=150)["Spoils"] == 1.8
    )  # (2.0+1.5)/2 -> 1.75


def test_suggest_z_falls_back_to_pooled_when_the_own_estimate_is_infinite():
    calibration = {"Odd": {"n": 500, "z_for_5pct": float("inf"), "z_for_10pct": float("inf")}}
    assert suggest_z(calibration, {0.05: 2.2, 0.10: 1.6}, _target)["Odd"] == 2.2


def test_tier_z_pools_each_tier_to_its_own_target():
    # Durable: demand above base_lt by 0..19 over 20 cases; the 95th percentile need is 19
    durable = [_case("Keeps", 0, 10.0 + i) for i in range(20)]
    spoils = [_case("Spoils", 0, 10.0 + i) for i in range(20)]

    z = tier_z(durable + spoils, _target)

    assert z["durable"] == pytest.approx(19.0)  # 5 % of 20 = 1 case may miss
    assert z["shelf_life"] == pytest.approx(18.0)  # 10 % of 20 = 2 cases may miss


def test_holdout_check_scores_on_the_later_half_only():
    rows = [_case("Keeps", T, 10.0 + (i % 5)) for T in range(10) for i in range(10)]

    result = holdout_check(rows, _target)

    assert result["calibrated_on_cases"] == 50 and result["scored_on_cases"] == 50
    names = list(result["policies"])
    assert names[0] == "flat z=1.65" and names[-1] == "per category"
    assert any(n.startswith("per tier") for n in names)
    per_tier = next(p for n, p in result["policies"].items() if n.startswith("per tier"))
    assert 0.0 <= per_tier["overall"] <= 1.0
    assert result["tier_z"]["durable"] >= 0
