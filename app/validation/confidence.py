"""app/validation/confidence.py – Deterministic confidence score.

Scoring rules (documented here and exposed via docstring):

Starting score: 1.0

Deductions:
    Hard issue present (any):           -0.50 (applied once)
    DATE_TOO_OLD:                        -0.20
    ITEM_UNMATCHED (per item):           -0.15, capped at -0.45 total
    ITEM_LOW_MATCH (per item):           -0.05, capped at -0.20 total
    PRICE_OUTLIER (at least one):        -0.10 (applied once)

Clamped to [0, 1].

Status:
    "needs_review" if any hard issue OR any ITEM_UNMATCHED OR confidence < CONFIDENCE_THRESHOLD
    else "confirmed"

An unmatched item has no SKU, so it would be missing from stock and forecasts. One unmatched
item costs only 0.15, which lands exactly on the default 0.85 threshold and would be
auto-confirmed, so it forces review regardless of the score. Fixing it in review saves an alias.
"""
from __future__ import annotations

from app.validation.rules import Issue


def compute_confidence(
    issues: list[Issue],
    confidence_threshold: float = 0.85,
) -> tuple[float, str]:
    """Compute (confidence, status) from a list of issues.

    Args:
        issues: list of Issue from the validation pipeline.
        confidence_threshold: below this value → "needs_review".

    Returns:
        (confidence: float in [0,1], status: "confirmed" | "needs_review")
    """
    score = 1.0
    has_hard = any(i.severity == "hard" for i in issues)

    if has_hard:
        score -= 0.50

    if any(i.code == "DATE_TOO_OLD" for i in issues):
        score -= 0.20

    unmatched_count = sum(1 for i in issues if i.code == "ITEM_UNMATCHED")
    score -= min(unmatched_count * 0.15, 0.45)

    low_match_count = sum(1 for i in issues if i.code == "ITEM_LOW_MATCH")
    score -= min(low_match_count * 0.05, 0.20)

    if any(i.code == "PRICE_OUTLIER" for i in issues):
        score -= 0.10

    confidence = max(0.0, min(1.0, score))
    needs_review = has_hard or unmatched_count > 0 or confidence < confidence_threshold
    status = "needs_review" if needs_review else "confirmed"
    return confidence, status
