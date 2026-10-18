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


def shelf_life_risk(
    current_stock: float, weekly_forecast: float, shelf_life_days: int | None
) -> str | None:
    """Will today's stock sell before it spoils? 'high' if it lasts longer than the shelf life,
    'watch' above 70 % of it, else None.

    This compares days of cover with the shelf life; it does not know how old the stock already
    is, because receiving dates per batch are not recorded.
    """
    if shelf_life_days is None or current_stock <= 0:
        return None
    cover = days_until_stockout(current_stock, weekly_forecast)
    if cover > shelf_life_days:
        return "high"
    if cover > 0.7 * shelf_life_days:
        return "watch"
    return None


def cap_order_for_shelf_life(
    order_qty: int, current_stock: float, weekly_forecast: float, shelf_life_days: int | None
) -> int:
    """Do not order more than can be sold before the shelf life ends (stock + order <= demand)."""
    if shelf_life_days is None:
        return order_qty
    sellable = weekly_forecast * shelf_life_days / 7.0
    return max(0, min(order_qty, math.floor(sellable - current_stock)))


def restock_reason(
    sku_name: str,
    current_stock: float,
    unit: str,
    weekly_forecast: float,
    days_out: float,
    lead_time_days: int,
    lang: str = "id",
) -> str:
    """Template-based reason string, in Indonesian ("id") or English ("en")."""
    stock_str = f"{current_stock:,.0f}"
    fc_str = f"{weekly_forecast:.1f}"
    never = days_out == float("inf")

    if lang == "en":
        days_str = "not computable (zero demand)" if never else f"in about {days_out:.0f} days"
        return (
            f"Stock {stock_str} {unit}, expected to sell {fc_str} {unit}/week, "
            f"runs out {days_str}. Lead time {lead_time_days} days."
        )
    days_str = "tidak terhitung (permintaan nol)" if never else f"sekitar {days_out:.0f} hari"
    return (
        f"Stok {stock_str} {unit}, perkiraan laku {fc_str} {unit}/minggu, "
        f"habis {days_str}. Lead time {lead_time_days} hari."
    )
