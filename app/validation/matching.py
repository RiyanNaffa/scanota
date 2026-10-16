"""app/validation/matching.py – Fuzzy product name matching.

normalize(text) -> str
    Lowercase, strip punctuation (keep digits and dots), collapse whitespace.

match_item(name, catalog_aliases) -> MatchResult
    Uses rapidfuzz WRatio on normalized strings.
    Levels:
        "auto"    if score >= MATCH_AUTO_THRESHOLD
        "suggest" if score >= MATCH_SUGGEST_THRESHOLD
        "none"    otherwise
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz


@dataclass
class MatchResult:
    sku_id: str | None
    score: float
    level: str  # "auto" | "suggest" | "none"


def normalize(text: str) -> str:
    """Lowercase, remove punctuation except digits and '.', collapse whitespace."""
    if not text:
        return ""
    text = text.lower()
    # Keep digits, letters (including unicode/accented), dots, whitespace
    text = re.sub(r"[^\w\d.\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_item(
    name: str,
    catalog_aliases: list[dict[str, Any]],
    auto_threshold: float = 90.0,
    suggest_threshold: float = 70.0,
) -> MatchResult:
    """Match a raw item name against the catalog.

    Args:
        name: raw item name as written on the receipt.
        catalog_aliases: list of dicts with keys "alias_norm" and "sku_id".
        auto_threshold: score >= this → level "auto".
        suggest_threshold: score >= this → level "suggest".

    Returns:
        MatchResult with the best matching SKU (or None).
    """
    if not name or not catalog_aliases:
        return MatchResult(sku_id=None, score=0.0, level="none")

    norm_name = normalize(name)

    best_score = 0.0
    best_sku: str | None = None

    for entry in catalog_aliases:
        alias_norm: str = entry.get("alias_norm", "")
        sku_id: str = entry.get("sku_id", "")

        # Exact normalized match → score 100
        if alias_norm == norm_name:
            return MatchResult(sku_id=sku_id, score=100.0, level="auto")

        score = fuzz.WRatio(norm_name, alias_norm)
        if score > best_score:
            best_score = score
            best_sku = sku_id

    if best_score >= auto_threshold:
        level = "auto"
    elif best_score >= suggest_threshold:
        level = "suggest"
    else:
        level = "none"
        best_sku = None

    return MatchResult(sku_id=best_sku, score=best_score, level=level)


def build_issue_from_match(
    item_name_raw: str,
    match: MatchResult,
    item_index: int,
) -> list[Any]:
    """Build validation issues based on match level (import Issue from rules)."""
    from app.validation.rules import Issue

    issues = []
    if match.level == "none":
        issues.append(
            Issue(
                code="ITEM_UNMATCHED",
                severity="soft",
                message=f"Item {item_index+1} '{item_name_raw}' could not be matched to any SKU",
                field=f"items[{item_index}].item_name_raw",
            )
        )
    elif match.level == "suggest":
        issues.append(
            Issue(
                code="ITEM_LOW_MATCH",
                severity="soft",
                message=(
                    f"Item {item_index+1} '{item_name_raw}' matched to SKU "
                    f"'{match.sku_id}' with low confidence (score={match.score:.0f})"
                ),
                field=f"items[{item_index}].item_name_raw",
            )
        )
    return issues
