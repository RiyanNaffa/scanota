"""tests/unit/test_category_policy.py – Per-category z and shelf life."""
from __future__ import annotations

import csv
import os

import pytest

from app.forecast.category_policy import (
    CATEGORY_POLICY,
    DURABLE_TARGET,
    DURABLE_Z,
    SHELF_LIFE_TARGET,
    SHELF_LIFE_Z,
    policy_for,
    target_stockout,
    z_by_category,
    z_for,
)

PRODUCTS_CSV = os.path.join("data", "sample_transactions", "products.csv")


def test_every_catalog_category_has_a_policy():
    """A new category must be a conscious decision, not a silent default."""
    with open(PRODUCTS_CSV, encoding="utf-8") as f:
        categories = {row["category"] for row in csv.DictReader(f)}

    assert categories - set(CATEGORY_POLICY) == set()


def test_every_policy_sets_a_positive_z():
    for category, policy in CATEGORY_POLICY.items():
        assert policy.z is not None and policy.z > 0, category


def test_shelf_life_goods_get_a_lower_z_than_durable_goods():
    assert SHELF_LIFE_Z < DURABLE_Z
    assert z_for("Semen", 9.9) == SHELF_LIFE_Z
    assert z_for("Pasir & Batu", 9.9) == DURABLE_Z


@pytest.mark.parametrize(
    ("category", "shelf_days"),
    [("Semen", 90), ("Semen & Plester", 180), ("Cat", 365), ("Waterproofing", 365), ("Kayu", None)],
)
def test_shelf_life_days(category, shelf_days):
    assert policy_for(category).shelf_life_days == shelf_days


def test_unknown_or_missing_category_uses_the_default_z_and_never_spoils():
    for category in ("Barang Baru", "", None):
        assert z_for(category, 2.2) == 2.2
        assert policy_for(category).shelf_life_days is None


def test_targets_follow_shelf_life():
    assert target_stockout("Semen") == SHELF_LIFE_TARGET
    assert target_stockout("Kayu") == DURABLE_TARGET
    assert target_stockout(None) == DURABLE_TARGET


def test_z_by_category_lists_every_configured_category():
    assert z_by_category(1.0) == {c: p.z for c, p in CATEGORY_POLICY.items()}
