"""app/forecast/category_policy.py – Reorder policy per product category: service level and shelf life.

A single z for every product is wrong in both directions. Sand and tiles cost little to keep and a
stockout loses the sale, so they deserve a high z. Cement clumps, and paint and waterproofing
expire, so over-stocking them wastes money and a slightly lower service level is acceptable.

The z values come from `make backtest` (docs/BUILD_LOG.md has the run). Two tiers, not 13 separate
numbers: calibrating each category on its own (3-4 SKUs, 45-225 cases) was noise. Calibrated on the
earlier half of the history and scored on the later half, per-category z gave 13.5 % stockouts on
the shelf-life goods against a 10 % target, while one z per tier gave 10.6 % (durable: 5.7 % vs 5 %).
Each category still has its own entry, so a real shop with more data can tune it separately.

Categories not listed here use SAFETY_STOCK_Z (also the durable value) and have no shelf life.
Shelf lives are rough defaults for sealed stock in a dry store: confirm them against the
supplier's label before relying on the warnings.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryPolicy:
    z: float | None = None  # safety-stock multiplier; None = use SAFETY_STOCK_Z
    shelf_life_days: int | None = None  # None = does not spoil in practice


DURABLE_Z = 2.2  # backtest: 5 % stockouts needs z of 2.17 on the full period (2.12 on the earlier half)
SHELF_LIFE_Z = 1.8  # backtest: 10 % stockouts needs 1.81 (1.81 on the earlier half)

CATEGORY_POLICY: dict[str, CategoryPolicy] = {
    # Keeps for years: a stockout costs the sale, holding costs only money and space.
    "Alat": CategoryPolicy(z=DURABLE_Z),
    "Kabel & Listrik": CategoryPolicy(z=DURABLE_Z),
    "Kayu": CategoryPolicy(z=DURABLE_Z),
    "Keramik": CategoryPolicy(z=DURABLE_Z),
    "Paku & Sekrup": CategoryPolicy(z=DURABLE_Z),
    "Panel": CategoryPolicy(z=DURABLE_Z),
    "Pasir & Batu": CategoryPolicy(z=DURABLE_Z),
    "Pipa & Fitting": CategoryPolicy(z=DURABLE_Z),
    "Tangki Air": CategoryPolicy(z=DURABLE_Z),
    # Has a shelf life: over-stocking can end in waste, so a looser service level.
    "Semen": CategoryPolicy(z=SHELF_LIFE_Z, shelf_life_days=90),
    "Semen & Plester": CategoryPolicy(z=SHELF_LIFE_Z, shelf_life_days=180),
    "Cat": CategoryPolicy(z=SHELF_LIFE_Z, shelf_life_days=365),
    "Waterproofing": CategoryPolicy(z=SHELF_LIFE_Z, shelf_life_days=365),
}


DURABLE_TARGET = 0.05  # stockout rate aimed at for goods that keep
SHELF_LIFE_TARGET = 0.10  # looser for goods that spoil: an extra stockout costs less than waste


def target_stockout(category: str | None) -> float:
    """Stockout rate a category's z is calibrated for (see app/eval/backtest.py)."""
    return SHELF_LIFE_TARGET if policy_for(category).shelf_life_days else DURABLE_TARGET


def policy_for(category: str | None) -> CategoryPolicy:
    return CATEGORY_POLICY.get(category or "", CategoryPolicy())


def z_for(category: str | None, default_z: float) -> float:
    z = policy_for(category).z
    return default_z if z is None else z


def z_by_category(default_z: float) -> dict[str, float]:
    """Explicit z per configured category, for the backtest."""
    return {c: (p.z if p.z is not None else default_z) for c, p in CATEGORY_POLICY.items()}
