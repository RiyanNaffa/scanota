"""app/validation/rules.py – Deterministic validation rules for extracted transactions.

Each rule function accepts the extraction dict and returns a (possibly empty) list of Issue.

Issue fields:
    code      – short UPPER_SNAKE identifier
    severity  – "hard" | "soft"
    message   – human-readable description
    field     – which field triggered the issue (or None)
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class Issue:
    code: str
    severity: str  # "hard" | "soft"
    message: str
    field: str | None = None


_FIVE_YEARS_DAYS = 5 * 365


def check_total_mismatch(
    items: list[dict],
    total: int | None,
    tolerance: int = 0,
) -> list[Issue]:
    """TOTAL_MISMATCH (hard): sum of line_totals does not equal total."""
    if total is None:
        return []
    line_sum = sum(int(item.get("line_total") or 0) for item in items)
    if abs(line_sum - int(total)) > tolerance:
        return [
            Issue(
                code="TOTAL_MISMATCH",
                severity="hard",
                message=(
                    f"Sum of line totals ({line_sum:,}) does not match "
                    f"total ({total:,}); difference {abs(line_sum - total):,}"
                ),
                field="total",
            )
        ]
    return []


def check_line_mismatch(items: list[dict]) -> list[Issue]:
    """LINE_MISMATCH (hard): qty * unit_price != line_total for any item."""
    issues = []
    for i, item in enumerate(items):
        qty = item.get("qty")
        unit_price = item.get("unit_price")
        line_total = item.get("line_total")
        if qty is None or unit_price is None or line_total is None:
            continue
        computed = Decimal(str(qty)) * Decimal(str(unit_price))
        actual = Decimal(str(line_total))
        # Allow rounding to whole Rupiah
        if abs(computed - actual) > Decimal("1"):
            issues.append(
                Issue(
                    code="LINE_MISMATCH",
                    severity="hard",
                    message=(
                        f"Item {i+1} '{item.get('item_name_raw', '')}': "
                        f"qty {qty} × price {unit_price} = {float(computed):,.0f} "
                        f"but line_total is {line_total}"
                    ),
                    field=f"items[{i}].line_total",
                )
            )
    return issues


def check_date(
    date_str: str | None,
    today: datetime.date | None = None,
) -> list[Issue]:
    """DATE_INVALID (hard), DATE_FUTURE (hard), DATE_TOO_OLD (soft)."""
    if today is None:
        today = datetime.date.today()
    issues: list[Issue] = []

    if not date_str:
        return [Issue(code="DATE_INVALID", severity="hard", message="Date is missing", field="date")]

    try:
        tx_date = datetime.date.fromisoformat(str(date_str))
    except (ValueError, TypeError):
        return [
            Issue(
                code="DATE_INVALID",
                severity="hard",
                message=f"Unparsable date: {date_str!r}",
                field="date",
            )
        ]

    if tx_date > today:
        issues.append(
            Issue(
                code="DATE_FUTURE",
                severity="hard",
                message=f"Transaction date {tx_date} is in the future",
                field="date",
            )
        )

    age_days = (today - tx_date).days
    if age_days > _FIVE_YEARS_DAYS:
        issues.append(
            Issue(
                code="DATE_TOO_OLD",
                severity="soft",
                message=f"Transaction date {tx_date} is more than 5 years ago",
                field="date",
            )
        )

    return issues


def check_no_items(items: list[dict] | None) -> list[Issue]:
    """NO_ITEMS (hard): item list is absent or empty."""
    if not items:
        return [Issue(code="NO_ITEMS", severity="hard", message="No items found", field="items")]
    return []


def check_qty_invalid(items: list[dict]) -> list[Issue]:
    """QTY_INVALID (hard): any item has a null, zero, or negative qty."""
    issues = []
    for i, item in enumerate(items):
        qty = item.get("qty")
        try:
            if qty is None or float(qty) <= 0:
                raise ValueError
        except (ValueError, TypeError):
            issues.append(
                Issue(
                    code="QTY_INVALID",
                    severity="hard",
                    message=f"Item {i+1} has invalid qty: {qty!r}",
                    field=f"items[{i}].qty",
                )
            )
    return issues


def check_price_outlier(
    items: list[dict],
    price_stats: dict[str, dict[str, Any]],
) -> list[Issue]:
    """PRICE_OUTLIER (soft): unit_price is < 0.5x or > 2x historical median.

    price_stats maps sku_id -> {"median": float, "count": int}.
    Only applied when count >= 5.
    """
    issues = []
    for i, item in enumerate(items):
        sku_id = item.get("sku_id")
        unit_price = item.get("unit_price")
        if not sku_id or unit_price is None:
            continue
        stats = price_stats.get(sku_id)
        if not stats or stats.get("count", 0) < 5:
            continue
        median = stats["median"]
        if median <= 0:
            continue
        price_val = float(unit_price)
        if price_val < 0.5 * median or price_val > 2.0 * median:
            issues.append(
                Issue(
                    code="PRICE_OUTLIER",
                    severity="soft",
                    message=(
                        f"Item {i+1} '{item.get('item_name_raw', '')}' unit_price "
                        f"{unit_price:,} is outside 0.5×–2× historical median "
                        f"{median:,.0f}"
                    ),
                    field=f"items[{i}].unit_price",
                )
            )
    return issues
