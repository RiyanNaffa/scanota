"""app/validation/pipeline.py – Orchestrates all validation rules.

validate_extraction(extraction, catalog, price_stats, today) -> ValidationResult
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.validation.confidence import compute_confidence
from app.validation.matching import MatchResult, build_issue_from_match, match_item
from app.validation.rules import (
    Issue,
    check_date,
    check_line_mismatch,
    check_no_items,
    check_price_outlier,
    check_qty_invalid,
    check_total_mismatch,
)


@dataclass
class ItemWithMatch:
    item_name_raw: str
    qty: Any
    unit: str | None
    unit_price: Any
    line_total: Any
    sku_id: str | None
    match_score: float
    match_level: str


@dataclass
class ValidationResult:
    items_with_matches: list[ItemWithMatch]
    issues: list[Issue]
    confidence: float
    status: str  # "confirmed" | "needs_review"


def validate_extraction(
    extraction: dict[str, Any],
    catalog: list[dict[str, Any]],
    price_stats: dict[str, dict[str, Any]] | None = None,
    today: datetime.date | None = None,
) -> ValidationResult:
    """Validate a raw extraction dict and match item names to SKUs.

    Args:
        extraction: dict with keys: date, customer, items, total.
        catalog: list of {"alias_norm": str, "sku_id": str} dicts.
        price_stats: maps sku_id -> {"median": float, "count": int}.
        today: for date validation (defaults to datetime.date.today()).

    Returns:
        ValidationResult with matched items, all issues, confidence and status.
    """
    settings = get_settings()
    if price_stats is None:
        price_stats = {}
    if today is None:
        today = datetime.date.today()

    issues: list[Issue] = []
    items_raw: list[dict] = extraction.get("items") or []

    # --- Structural checks ---
    issues += check_no_items(items_raw)
    issues += check_date(extraction.get("date"), today=today)
    issues += check_qty_invalid(items_raw)

    # --- Match items to SKUs ---
    items_with_matches: list[ItemWithMatch] = []
    for i, item in enumerate(items_raw):
        match: MatchResult = match_item(
            item.get("item_name_raw", ""),
            catalog,
            auto_threshold=settings.match_auto_threshold,
            suggest_threshold=settings.match_suggest_threshold,
        )
        # Attach sku_id back to item dict so subsequent rules can use it
        item = dict(item)
        item["sku_id"] = match.sku_id

        issues += build_issue_from_match(
            item.get("item_name_raw", ""), match, item_index=i
        )
        items_with_matches.append(
            ItemWithMatch(
                item_name_raw=item.get("item_name_raw", ""),
                qty=item.get("qty"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                line_total=item.get("line_total"),
                sku_id=match.sku_id,
                match_score=match.score,
                match_level=match.level,
            )
        )

    # --- Financial checks ---
    issues += check_line_mismatch(items_raw)
    issues += check_total_mismatch(
        items_raw,
        extraction.get("total"),
        tolerance=settings.total_tolerance,
    )
    issues += check_price_outlier(items_raw, price_stats)

    confidence, status = compute_confidence(issues, settings.confidence_threshold)

    return ValidationResult(
        items_with_matches=items_with_matches,
        issues=issues,
        confidence=confidence,
        status=status,
    )
