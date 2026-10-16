"""app/forecast/service.py – Forecast service: build series and compute restock."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import get_products
from app.forecast.models import build_weekly_series, forecast_sku
from app.forecast.policy import (
    action,
    days_until_stockout,
    lead_time_weeks,
    order_quantity,
    reorder_point,
    restock_reason,
    safety_stock,
)

logger = logging.getLogger(__name__)


def get_confirmed_item_sales(db: Session) -> list[dict[str, Any]]:
    """Return sku_id, tx_date, qty from confirmed transactions."""
    from sqlalchemy import text

    rows = db.execute(
        text(
            "SELECT i.sku_id, t.tx_date, i.qty "
            "FROM transaction_items i "
            "JOIN transactions t ON t.id = i.transaction_id "
            "WHERE t.status = 'confirmed' AND i.sku_id IS NOT NULL"
        )
    ).fetchall()
    return [{"sku_id": r[0], "tx_date": str(r[1]), "qty": float(r[2])} for r in rows]


def build_restock_list(db: Session) -> list[dict[str, Any]]:
    """Compute restock recommendations for all products."""
    settings = get_settings()
    products = get_products(db)
    sales = get_confirmed_item_sales(db)
    series_map = build_weekly_series(sales)

    results = []
    for product in products:
        sku_id = product["sku_id"]
        current_stock = float(product.get("current_stock") or 0)
        ltd = int(product.get("lead_time_days") or 3)
        unit = product.get("unit", "pcs")
        name = product.get("name", sku_id)
        category = product.get("category", "")

        series = series_map.get(sku_id)
        if series is not None:
            fc_result = forecast_sku(series, horizon=2)
        else:
            fc_result = {
                "forecast": [0.0, 0.0],
                "model_used": "WindowAverage(no_data)",
                "sigma": 0.0,
                "is_fallback": True,
                "wape_primary": None,
                "wape_baseline": None,
            }

        weekly_fc = sum(fc_result["forecast"]) / max(len(fc_result["forecast"]), 1)
        sigma = fc_result["sigma"]
        lt_wks = lead_time_weeks(ltd)

        ss = safety_stock(sigma, lt_wks, z=settings.safety_stock_z)
        rop = reorder_point(weekly_fc * lt_wks, ss)
        order_qty = order_quantity(weekly_fc, lt_wks, ss, current_stock)
        days_out = days_until_stockout(current_stock, weekly_fc)
        act = action(current_stock, rop)
        reason = restock_reason(name, current_stock, unit, weekly_fc, days_out, ltd)

        data_quality = "insufficient_history" if fc_result["is_fallback"] else "ok"

        results.append({
            "sku_id": sku_id,
            "name": name,
            "category": category,
            "unit": unit,
            "current_stock": current_stock,
            "forecast_next_2_weeks": fc_result["forecast"],
            "model_used": fc_result["model_used"],
            "days_until_stockout": days_out if days_out != float("inf") else None,
            "reorder_point": round(rop, 2),
            "suggested_order_qty": order_qty,
            "action": act,
            "reason": reason,
            "data_quality": data_quality,
            "wape_primary": fc_result["wape_primary"],
            "wape_baseline": fc_result["wape_baseline"],
        })

    # Sort by urgency: order_now first, then watch, then ok
    urgency = {"order_now": 0, "watch": 1, "ok": 2}
    results.sort(key=lambda r: (urgency.get(r["action"], 3), r.get("days_until_stockout") or 9999))
    return results


def get_forecast_series(db: Session, sku_id: str) -> dict[str, Any] | None:
    """Return historical + forecast series for a SKU (for chart display)."""
    sales = get_confirmed_item_sales(db)
    series_map = build_weekly_series(sales)
    series = series_map.get(sku_id)
    if series is None:
        return None

    fc_result = forecast_sku(series, horizon=4)
    sigma = fc_result["sigma"]

    history = [
        {"week": str(p), "qty": float(v)}
        for p, v in zip(series.index, series.values, strict=False)
    ]
    fc_weeks = []
    last_period = series.index[-1]
    for i, v in enumerate(fc_result["forecast"]):
        next_p = last_period + (i + 1)
        fc_weeks.append({
            "week": str(next_p),
            "qty": v,
            "lower": max(0.0, v - 1.65 * sigma),
            "upper": v + 1.65 * sigma,
        })

    return {
        "sku_id": sku_id,
        "history": history,
        "forecast": fc_weeks,
        "model_used": fc_result["model_used"],
        "sigma": sigma,
    }
