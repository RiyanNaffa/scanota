"""app/forecast/policy.py – Deterministic reorder policy (pure functions, unit-tested).

All inputs/outputs are plain Python numbers. No database, no ORM.
"""
from __future__ import annotations

import math


def lead_time_weeks(lead_time_days: float) -> float:
    return lead_time_days / 7.0


def demand_during_lead_time(weekly_forecast: float, lt_weeks: float) -> float:
    return weekly_forecast * lt_weeks


def safety_stock(
    sigma: float,
    lt_weeks: float,
    z: float = 1.65,
) -> float:
    """Safety stock = z * sigma * sqrt(lead_time_weeks)."""
    if lt_weeks <= 0 or sigma <= 0:
        return 0.0
    return z * sigma * math.sqrt(lt_weeks)


def reorder_point(demand_lt: float, ss: float) -> float:
    return demand_lt + ss


def order_quantity(
    weekly_forecast: float,
    lt_weeks: float,
    ss: float,
    current_stock: float,
    review_weeks: float = 1.0,
) -> int:
    """Order quantity rounded UP to whole units. Returns 0 if no order needed."""
    target = weekly_forecast * (lt_weeks + review_weeks) + ss
    qty = target - current_stock
    return max(0, math.ceil(qty))


def days_until_stockout(current_stock: float, weekly_forecast: float) -> float:
    """Return days until stockout. Returns infinity if weekly_forecast == 0."""
    if weekly_forecast <= 0:
        return float("inf")
    return current_stock / (weekly_forecast / 7.0)


def action(current_stock: float, rop: float) -> str:
    """Reorder action: 'order_now', 'watch', or 'ok'."""
    if current_stock <= rop:
        return "order_now"
    if current_stock <= rop * 1.5:
        return "watch"
    return "ok"


def restock_reason(
    sku_name: str,
    current_stock: float,
    unit: str,
    weekly_forecast: float,
    days_out: float,
    lead_time_days: int,
) -> str:
    """Template-based reason string in Indonesian."""
    stock_str = f"{current_stock:,.0f}"
    fc_str = f"{weekly_forecast:.1f}"
    lt_str = str(lead_time_days)

    if days_out == float("inf"):
        days_str = "tidak terhitung (permintaan nol)"
    else:
        days_str = f"sekitar {days_out:.0f} hari"

    return (
        f"Stok {stock_str} {unit}, perkiraan laku {fc_str} {unit}/minggu, "
        f"habis {days_str}. Lead time {lt_str} hari."
    )
