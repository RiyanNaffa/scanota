"""app/eval/backtest.py – Rolling-origin backtest of the restock forecast and safety stock.

Run (needs the stack up and the seed loaded):  make backtest
    docker compose exec api python -m app.eval.backtest [--origins 26] [--json out.json]

For each SKU and each of the last N weeks (the "origin"), using only data from before that week:
  1. forecast weekly demand and pick a sigma (the spread of forecast errors),
  2. size a reorder point:  rop = weekly_forecast * lead_time + z * sigma * sqrt(lead_time),
  3. look at the demand that really arrived during the lead time (daily dates, not weekly totals).
A stockout is realised lead-time demand above the reorder point. z = 1.65 aims at about 5 %.

Several sigma estimators are scored side by side, plus the 4-week moving-average baseline, so the
choice of estimator rests on numbers. The data is synthetic (app/synth/generate.py: 30 % zero
weeks, 30 % noise), so the results show how the method behaves on that process, not on a real shop.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from app.forecast import models
from app.forecast.metrics import rmse
from app.forecast.policy import lead_time_weeks, safety_stock

SIGMA_WINDOWS = tuple(sorted({8, 13, 26, models.SIGMA_LOOKBACK_WEEKS}))
SPARSE_ZERO_SHARE = 0.4  # SKUs with more than 40 % zero weeks are reported separately


def stockout_stats(rops: list[float], realised: list[float]) -> dict[str, float]:
    """Stockout rate, share of demand above the reorder point, and average reorder point."""
    r = np.asarray(rops, dtype=float)
    d = np.asarray(realised, dtype=float)
    if r.size == 0:
        return {"stockout_rate": 0.0, "unmet_pct": 0.0, "avg_rop": 0.0, "n": 0}
    total = float(d.sum())
    return {
        "stockout_rate": float(np.mean(d > r)),
        "unmet_pct": float(np.maximum(d - r, 0).sum() / total) if total > 0 else 0.0,
        "avg_rop": float(r.mean()),
        "n": int(r.size),
    }


def z_for_target(
    base_lt: list[float], scale: list[float], realised: list[float], target: float = 0.05
) -> float:
    """Smallest z whose stockout rate is at most `target`, given rop = base_lt + z * scale.

    scale is sigma * sqrt(lead time). Cases with scale 0 cannot be fixed by any z: they count
    as a stockout whenever demand exceeds base_lt, which can make the answer infinite.
    """
    b = np.asarray(base_lt, dtype=float)
    sc = np.asarray(scale, dtype=float)
    d = np.asarray(realised, dtype=float)
    if d.size == 0:
        return 0.0
    safe = np.where(sc > 0, sc, 1.0)
    need = np.where(sc > 0, (d - b) / safe, np.where(d > b, np.inf, -np.inf))
    return float(np.quantile(need, 1 - target, method="higher"))


def sigma_stability(scales_by_sku: dict[str, list[float]]) -> float:
    """Average over SKUs of std/mean of the sigma estimate across origins (lower = steadier)."""
    cvs = [np.std(v) / np.mean(v) for v in scales_by_sku.values() if len(v) >= 2 and np.mean(v) > 0]
    return float(np.mean(cvs)) if cvs else 0.0


def _category_calibration(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per category: number of cases and the z that would have given a 5 % / 10 % stockout rate."""
    out: dict[str, dict[str, float]] = {}
    for cat in sorted({r["category"] for r in rows}):
        sel = [r for r in rows if r["category"] == cat]
        cols = ([r["base_lt"] for r in sel], [r["scale"] for r in sel], [r["realised"] for r in sel])
        out[cat] = {"n": len(sel), "z_for_5pct": z_for_target(*cols, target=0.05),
                    "z_for_10pct": z_for_target(*cols, target=0.10)}
    return out


def _pooled_z(rows: list[dict[str, Any]]) -> dict[float, float]:
    cols = ([r["base_lt"] for r in rows], [r["scale"] for r in rows], [r["realised"] for r in rows])
    return {t: z_for_target(*cols, target=t) for t in (0.05, 0.10)}


def suggest_z(
    calibration: dict[str, dict[str, float]],
    pooled: dict[float, float],
    target_of: Callable[[str], float],
    k: float = 150.0,
) -> dict[str, float]:
    """z per category: its own calibrated z pulled toward the pooled z by n / (n + k).

    A category holds only a few SKUs, so its own estimate is noisy; k acts like k extra cases of
    pooled evidence. Rounded to 0.1. A non-finite estimate falls back to the pooled z.
    """
    out: dict[str, float] = {}
    for cat, s in calibration.items():
        target = target_of(cat)
        own = s["z_for_5pct"] if target <= 0.05 else s["z_for_10pct"]
        pool = pooled[0.05] if target <= 0.05 else pooled[0.10]
        if not math.isfinite(own):
            own = pool
        w = s["n"] / (s["n"] + k)
        out[cat] = round(w * own + (1 - w) * pool, 1)
    return out


def tier_z(rows: list[dict[str, Any]], target_of: Callable[[str], float]) -> dict[str, float]:
    """z per tier: durable goods aim at 5 % stockouts, goods with a shelf life at 10 %.

    A tier pools every category in it, so it rests on hundreds of cases instead of 45-225.
    """
    out: dict[str, float] = {}
    for tier, target in (("durable", 0.05), ("shelf_life", 0.10)):
        sel = [r for r in rows if (target_of(r["category"]) > 0.05) == (tier == "shelf_life")]
        cols = ([r["base_lt"] for r in sel], [r["scale"] for r in sel], [r["realised"] for r in sel])
        out[tier] = z_for_target(*cols, target=target) if sel else 0.0
    return out


def _miss_rate(rows: list[dict[str, Any]], z_of: Callable[[str], float]) -> float:
    if not rows:
        return 0.0
    return float(np.mean([r["realised"] > r["base_lt"] + z_of(r["category"]) * r["scale"] for r in rows]))


def holdout_check(
    rows: list[dict[str, Any]], target_of: Callable[[str], float], k: float = 150.0
) -> dict[str, Any]:
    """Calibrate z on the earlier half of the origins, then score it on the later half.

    Scoring the calibration data itself would flatter any z, so this is the number to trust.
    Compares flat z = 1.65, the pooled z for 5 %, and the per-category suggestion.
    """
    weeks = sorted({r["T"] for r in rows})
    split = weeks[len(weeks) // 2]
    train = [r for r in rows if r["T"] < split]
    test = [r for r in rows if r["T"] >= split]
    pooled = _pooled_z(train)
    z_cat = suggest_z(_category_calibration(train), pooled, target_of, k)
    flat = pooled[0.05]
    tz = tier_z(train, target_of)

    def by_tier(c: str) -> float:
        return tz["shelf_life" if target_of(c) > 0.05 else "durable"]

    policies: dict[str, Callable[[str], float]] = {
        "flat z=1.65": lambda c: 1.65,
        f"flat z={flat:.2f} (pooled 5%)": lambda c: flat,
        f"per tier ({tz['durable']:.2f} / {tz['shelf_life']:.2f})": by_tier,
        "per category": lambda c: z_cat.get(c, flat),
    }
    tiers = {"durable": [r for r in test if target_of(r["category"]) <= 0.05],
             "shelf_life": [r for r in test if target_of(r["category"]) > 0.05]}
    out: dict[str, dict[str, float]] = {}
    for name, z_of in policies.items():
        out[name] = {
            "overall": _miss_rate(test, z_of),
            "durable": _miss_rate(tiers["durable"], z_of),
            "shelf_life": _miss_rate(tiers["shelf_life"], z_of),
            "avg_safety_stock": float(np.mean([z_of(r["category"]) * r["scale"] for r in test])),
        }
    return {"calibrated_on_cases": len(train), "scored_on_cases": len(test),
            "z_by_category": z_cat, "tier_z": tz, "policies": out}


def lead_time_demand(daily: pd.Series, start: pd.Timestamp, lead_days: int) -> float:
    """Units sold on the lead_days days beginning at `start` (daily: qty indexed by date)."""
    end = start + pd.Timedelta(days=lead_days)
    return float(daily[(daily.index >= start) & (daily.index < end)].sum())


def _abs_std(errors: np.ndarray) -> float:
    """The sigma the code used before: spread of the error SIZES (kept only for comparison)."""
    return float(np.std(np.abs(errors))) if errors.size >= 2 else 0.0


def _window_sigmas(preds: dict[int, float], values: np.ndarray, T: int) -> dict[str, float]:
    sig: dict[str, float] = {}
    for w in SIGMA_WINDOWS:
        weeks = [t for t in range(T - w, T) if t in preds]
        e = np.array([preds[t] - values[t] for t in weeks])
        sig[f"rmse{w}"] = rmse(values[weeks], [preds[t] for t in weeks]) if len(weeks) >= 2 else 0.0
        if w == 8:
            sig["old_abs_std8"] = _abs_std(e)
    return sig


def run_backtest(
    sales: list[dict[str, Any]],
    lead_days: dict[str, int],
    origins: int = 26,
    z: float = 1.65,
    categories: dict[str, str] | None = None,
    z_by_category: dict[str, float] | None = None,
    target_of: Callable[[str], float] | None = None,
) -> dict[str, Any]:
    """Score every method on the last `origins` weeks. `sales` rows: sku_id, tx_date, qty.

    `categories` maps sku -> category; `z_by_category` overrides z per category (default z else).
    """
    if models._try_import_statsforecast()[0] is None:
        raise RuntimeError("statsforecast is not importable; the backtest needs the real models.")

    series_map = models.build_weekly_series(sales)
    df = pd.DataFrame(sales)
    df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.normalize()
    daily_by_sku = {k: g.groupby("tx_date")["qty"].sum() for k, g in df.groupby("sku_id")}

    methods = ["baseline_ma4", "old_abs_std8"] + [f"rmse{w}" for w in SIGMA_WINDOWS]
    records: list[dict[str, Any]] = []
    fc_err = {"scanota": [0.0, 0.0], "baseline": [0.0, 0.0]}  # [sum |a-f|, sum a] for next week
    sigma_mismatch = 0.0  # largest gap between forecast_sku's sigma and the precomputed one

    for sku, s in series_map.items():
        values = s.values.astype(float)
        n = len(values)
        if n < origins + max(SIGMA_WINDOWS) + models.MIN_HISTORY_WEEKS:
            continue
        sparse = float(np.mean(values == 0)) > SPARSE_ZERO_SHARE
        lead = int(lead_days.get(sku, 3))
        lt_wks = lead_time_weeks(lead)
        category = (categories or {}).get(sku, "?")
        z_sku = (z_by_category or {}).get(category, z)
        first = n - origins

        # One-step predictions per model, each made only from the weeks before it.
        pre: dict[str, dict[int, float]] = {}
        lo, hi = first - max(SIGMA_WINDOWS), n - 1
        for name in ("TSB", "CrostonOptimized"):
            actuals, preds = models.one_step_forecasts(name, values, s.index, lo, hi)
            pre[name] = {lo + i: p for i, p in enumerate(preds)} if len(preds) == hi - lo else {}

        for T in range(first, n):
            fc = models.forecast_sku(s.iloc[:T], horizon=2)
            if fc["is_fallback"] or fc["model_used"] not in pre or not pre[fc["model_used"]]:
                continue
            weekly_fc = sum(fc["forecast"]) / len(fc["forecast"])
            sig = _window_sigmas(pre[fc["model_used"]], values, T)
            ma4 = float(np.mean(values[T - models.WINDOW_SIZE:T]))
            sig["baseline_ma4"] = float(np.std(values[T - models.WINDOW_SIZE:T]))
            sigma_mismatch = max(sigma_mismatch, abs(fc["sigma"] - sig[f"rmse{models.SIGMA_LOOKBACK_WEEKS}"]))
            realised = lead_time_demand(daily_by_sku[sku], s.index[T].start_time, lead)

            for m in methods:
                base = ma4 if m == "baseline_ma4" else weekly_fc
                rop = base * lt_wks + safety_stock(sig[m], lt_wks, z=z_sku)
                records.append({"sku": sku, "T": T, "method": m, "rop": rop,
                                "ss": rop - base * lt_wks, "base_lt": base * lt_wks,
                                "scale": sig[m] * math.sqrt(lt_wks), "lead": lead,
                                "realised": realised, "sparse": sparse,
                                "category": category, "z": z_sku})
            fc_err["scanota"][0] += abs(values[T] - fc["forecast"][0])
            fc_err["baseline"][0] += abs(values[T] - ma4)
            fc_err["scanota"][1] += values[T]
            fc_err["baseline"][1] += values[T]

    by_method: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for m in methods:
        for label, pick in (("all", lambda r: True), ("sparse", lambda r: r["sparse"]),
                            ("regular", lambda r: not r["sparse"])):
            rows = [r for r in records if r["method"] == m and pick(r)]
            stats = stockout_stats([r["rop"] for r in rows], [r["realised"] for r in rows])
            stats["avg_safety_stock"] = float(np.mean([r["ss"] for r in rows])) if rows else 0.0
            by_method[m][label] = stats

    z_needed: dict[str, float] = {}
    stability: dict[str, float] = {}
    by_lead: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for m in methods:
        rows = [r for r in records if r["method"] == m]
        z_needed[m] = z_for_target([r["base_lt"] for r in rows], [r["scale"] for r in rows],
                                   [r["realised"] for r in rows])
        per_sku: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            per_sku[r["sku"]].append(r["scale"])
        stability[m] = sigma_stability(per_sku)
        for label, pick in (("lead<=3d", lambda r: r["lead"] <= 3), ("lead>3d", lambda r: r["lead"] > 3)):
            sel = [r for r in rows if pick(r)]
            by_lead[m][label] = stockout_stats([r["rop"] for r in sel], [r["realised"] for r in sel])

    # Per category, for the estimator production uses: stockout at the z in force, and the z that
    # would have hit 5 % and 10 %. Categories hold only a few SKUs, so read the counts with care.
    prod = f"rmse{models.SIGMA_LOOKBACK_WEEKS}"
    by_category: dict[str, dict[str, float]] = {}
    for cat in sorted({r["category"] for r in records}):
        rows = [r for r in records if r["method"] == prod and r["category"] == cat]
        cols = ([r["base_lt"] for r in rows], [r["scale"] for r in rows], [r["realised"] for r in rows])
        stats = stockout_stats([r["rop"] for r in rows], cols[2])
        stats.update(
            z=rows[0]["z"],
            skus=len({r["sku"] for r in rows}),
            avg_safety_stock=float(np.mean([r["ss"] for r in rows])),
            z_for_5pct=z_for_target(*cols, target=0.05),
            z_for_10pct=z_for_target(*cols, target=0.10),
        )
        by_category[cat] = stats

    target_of = target_of or (lambda c: 0.05)
    prod_rows = [r for r in records if r["method"] == prod]
    pooled = _pooled_z(prod_rows) if prod_rows else {0.05: 0.0, 0.10: 0.0}
    suggested = suggest_z(_category_calibration(prod_rows), pooled, target_of) if prod_rows else {}
    holdout = holdout_check(prod_rows, target_of) if len({r["T"] for r in prod_rows}) >= 2 else None
    tiers_full = tier_z(prod_rows, target_of) if prod_rows else {}

    def _wape(k: str) -> float:
        err, tot = fc_err[k]
        return err / tot if tot > 0 else float("nan")

    return {
        "origins": origins,
        "z": z,
        "skus": len({r["sku"] for r in records}),
        "wape_next_week": {"scanota": _wape("scanota"), "baseline": _wape("baseline")},
        "max_sigma_mismatch": sigma_mismatch,
        "methods": by_method,
        "z_needed_for_5pct": z_needed,
        "sigma_stability_cv": stability,
        "by_lead_time": by_lead,
        "category_method": prod,
        "by_category": by_category,
        "pooled_z": {"5pct": pooled[0.05], "10pct": pooled[0.10]},
        "suggested_z": suggested,
        "tier_z": tiers_full,
        "holdout": holdout,
    }


def format_report(result: dict[str, Any]) -> str:
    lines = [
        f"Backtest: {result['skus']} SKUs x last {result['origins']} weeks; z per category as in "
        f"category_policy.py (default {result['z']} elsewhere). Targets: 5% stockouts for goods "
        f"that keep, 10% for goods with a shelf life",
        "",
        f"WAPE of next-week forecast: scanota {result['wape_next_week']['scanota']:.3f} "
        f"vs 4-week moving average {result['wape_next_week']['baseline']:.3f}",
        f"Check: production sigma ({models.SIGMA_LOOKBACK_WEEKS} weeks) vs backtest, largest gap "
        f"{result['max_sigma_mismatch']:.2e}",
    ]
    for label in ("all", "regular", "sparse"):
        lines += ["", f"[{label} SKUs]", f"{'method':<14}{'stockout':>10}{'unmet demand':>14}"
                  f"{'avg safety':>12}{'avg rop':>10}{'n':>7}"]
        for m, per in result["methods"].items():
            s = per[label]
            lines.append(f"{m:<14}{s['stockout_rate']:>10.1%}{s['unmet_pct']:>14.1%}"
                         f"{s['avg_safety_stock']:>12.2f}{s['avg_rop']:>10.2f}{s['n']:>7}")
    lines += ["", "Calibration and stability", f"{'method':<14}{'z for 5%':>10}{'sigma CV':>10}"]
    for m in result["methods"]:
        z = result["z_needed_for_5pct"][m]
        lines.append(f"{m:<14}{z:>10.2f}{result['sigma_stability_cv'][m]:>10.2f}")
    labels = ("lead<=3d", "lead>3d")
    lines += ["", "Stockout rate by lead time",
              f"{'method':<14}" + "".join(f"{lab:>12}" for lab in labels) + f"{'n (<=3d / >3d)':>20}"]
    for m, per in result["by_lead_time"].items():
        counts = f"{per[labels[0]]['n']} / {per[labels[1]]['n']}"
        lines.append(f"{m:<14}" + "".join(f"{per[lab]['stockout_rate']:>12.1%}" for lab in labels)
                     + f"{counts:>20}")
    cats = result.get("by_category") or {}
    if cats:
        lines += ["", f"By category ({result['category_method']}, z as configured)",
                  f"{'category':<17}{'SKUs':>5}{'cases':>7}{'z':>6}{'stockout':>10}{'unmet':>8}"
                  f"{'avg safety':>12}{'z for 5%':>10}{'z for 10%':>11}"]
        for cat, s in cats.items():
            lines.append(f"{cat:<17}{s['skus']:>5}{s['n']:>7}{s['z']:>6.2f}{s['stockout_rate']:>10.1%}"
                         f"{s['unmet_pct']:>8.1%}{s['avg_safety_stock']:>12.2f}"
                         f"{s['z_for_5pct']:>10.2f}{s['z_for_10pct']:>11.2f}")
    sug = result.get("suggested_z") or {}
    if sug:
        lines += ["", "Suggested z per category (own estimate pulled toward the pooled z: "
                      f"{result['pooled_z']['5pct']:.2f} for 5%, {result['pooled_z']['10pct']:.2f} for 10%)"]
        lines.append("  " + ", ".join(f"{c}: {z}" for c, z in sug.items()))
    tiers = result.get("tier_z") or {}
    if tiers:
        lines += ["", f"z per tier on the full period: durable (5% target) {tiers['durable']:.2f}, "
                      f"shelf life (10% target) {tiers['shelf_life']:.2f}"]
    ho = result.get("holdout")
    if ho:
        lines += ["", f"Out-of-sample check: z calibrated on {ho['calibrated_on_cases']} earlier cases, "
                      f"scored on {ho['scored_on_cases']} later ones",
                  f"{'policy':<28}{'overall':>9}{'durable':>9}{'shelf life':>12}{'avg safety':>12}"]
        for name, p in ho["policies"].items():
            lines.append(f"{name:<28}{p['overall']:>9.1%}{p['durable']:>9.1%}"
                         f"{p['shelf_life']:>12.1%}{p['avg_safety_stock']:>12.2f}")
        lines.append("  targets: durable 5%, shelf-life 10%")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--origins", type=int, default=26, help="weeks to evaluate (default 26)")
    parser.add_argument("--json", help="also write the raw result to this path")
    args = parser.parse_args()

    from app.config import get_settings
    from app.db.repository import get_products
    from app.db.session import SessionLocal
    from app.forecast.category_policy import target_stockout, z_by_category
    from app.forecast.service import get_confirmed_item_sales

    db = SessionLocal()
    try:
        sales = get_confirmed_item_sales(db)
        products = get_products(db)
    finally:
        db.close()
    lead_days = {p["sku_id"]: int(p.get("lead_time_days") or 3) for p in products}
    categories = {p["sku_id"]: p.get("category") or "?" for p in products}

    default_z = get_settings().safety_stock_z
    result = run_backtest(
        sales, lead_days, origins=args.origins, z=default_z,
        categories=categories, z_by_category=z_by_category(default_z), target_of=target_stockout,
    )
    print(format_report(result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
