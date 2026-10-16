"""tests/unit/test_validation.py – Comprehensive unit tests for the validation core.

Covers: parse_rupiah, rules, matching, confidence. >= 40 test cases.
No network, no database required.
"""
from __future__ import annotations

import datetime

import pytest

from app.validation.confidence import compute_confidence
from app.validation.matching import match_item, normalize
from app.validation.money import parse_rupiah
from app.validation.pipeline import validate_extraction
from app.validation.rules import (
    Issue,
    check_date,
    check_line_mismatch,
    check_no_items,
    check_price_outlier,
    check_qty_invalid,
    check_total_mismatch,
)

# ==========================================================================
# parse_rupiah – 15 cases
# ==========================================================================


class TestParseRupiah:
    def test_plain_integer(self):
        assert parse_rupiah(25000) == 25000

    def test_zero(self):
        assert parse_rupiah(0) == 0

    def test_integral_float(self):
        assert parse_rupiah(25000.0) == 25000

    def test_string_plain(self):
        assert parse_rupiah("25000") == 25000

    def test_string_dot_thousands(self):
        assert parse_rupiah("1.250.000") == 1250000

    def test_string_comma_thousands(self):
        assert parse_rupiah("1,250,000") == 1250000

    def test_string_rp_prefix_spaced(self):
        assert parse_rupiah("Rp 25.000") == 25000

    def test_string_rp_prefix_nospace(self):
        assert parse_rupiah("Rp25000") == 25000

    def test_string_trailing_dash(self):
        assert parse_rupiah(" 25.000,- ") == 25000

    def test_string_trailing_zero_decimal(self):
        # "1.250.000,00" → 1250000
        assert parse_rupiah("1.250.000,00") == 1250000

    def test_string_single_dot_group(self):
        assert parse_rupiah("25.000") == 25000

    def test_negative_int_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah(-100)

    def test_negative_float_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah(-1.0)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah("")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah("abc")

    def test_fractional_float_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah(25000.50)

    def test_bool_raises(self):
        with pytest.raises(ValueError):
            parse_rupiah(True)


# ==========================================================================
# check_total_mismatch – passing, failing, boundary
# ==========================================================================


class TestTotalMismatch:
    def test_pass_exact(self):
        items = [{"line_total": 500}, {"line_total": 500}]
        assert check_total_mismatch(items, total=1000, tolerance=0) == []

    def test_fail_mismatch(self):
        items = [{"line_total": 500}, {"line_total": 600}]
        issues = check_total_mismatch(items, total=1000, tolerance=0)
        assert len(issues) == 1
        assert issues[0].code == "TOTAL_MISMATCH"
        assert issues[0].severity == "hard"

    def test_boundary_off_by_one_no_tolerance(self):
        items = [{"line_total": 999}]
        issues = check_total_mismatch(items, total=1000, tolerance=0)
        assert len(issues) == 1

    def test_boundary_within_tolerance(self):
        items = [{"line_total": 999}]
        issues = check_total_mismatch(items, total=1000, tolerance=1)
        assert issues == []

    def test_none_total_skipped(self):
        items = [{"line_total": 500}]
        assert check_total_mismatch(items, total=None, tolerance=0) == []


# ==========================================================================
# check_line_mismatch – passing, failing, boundary
# ==========================================================================


class TestLineMismatch:
    def test_pass_exact(self):
        items = [{"qty": 2, "unit_price": 500, "line_total": 1000}]
        assert check_line_mismatch(items) == []

    def test_fail_wrong_total(self):
        # 2 × 500 = 1000; line_total 888 → difference 112 > 1 → hard issue
        items = [{"qty": 2, "unit_price": 500, "line_total": 888}]
        issues = check_line_mismatch(items)
        assert len(issues) == 1
        assert issues[0].code == "LINE_MISMATCH"

    def test_boundary_rounding_allowed(self):
        # 3 × 333 = 999; line_total 1000 → diff = 1 → allowed (rounding)
        items = [{"qty": 3, "unit_price": 333, "line_total": 1000}]
        assert check_line_mismatch(items) == []

    def test_null_fields_skipped(self):
        items = [{"qty": None, "unit_price": 500, "line_total": None}]
        assert check_line_mismatch(items) == []


# ==========================================================================
# check_date – passing, failing, boundary
# ==========================================================================


TODAY = datetime.date(2025, 7, 14)


class TestDate:
    def test_valid_date(self):
        assert check_date("2025-07-01", today=TODAY) == []

    def test_missing_date(self):
        issues = check_date(None, today=TODAY)
        assert any(i.code == "DATE_INVALID" for i in issues)
        assert any(i.severity == "hard" for i in issues)

    def test_unparsable_date(self):
        issues = check_date("not-a-date", today=TODAY)
        assert any(i.code == "DATE_INVALID" for i in issues)

    def test_future_date(self):
        issues = check_date("2099-01-01", today=TODAY)
        assert any(i.code == "DATE_FUTURE" for i in issues)

    def test_too_old_date(self):
        issues = check_date("2010-01-01", today=TODAY)
        assert any(i.code == "DATE_TOO_OLD" for i in issues)
        assert all(i.severity in ("hard", "soft") for i in issues)

    def test_exactly_five_years(self):
        # Exactly 5*365 days ago is right at the boundary – the check is > 5*365 days
        import datetime as dt

        date_val = TODAY - dt.timedelta(days=5 * 365)
        issues = check_date(date_val.isoformat(), today=TODAY)
        # age == 5*365 is NOT greater than _FIVE_YEARS_DAYS, so no DATE_TOO_OLD
        assert not any(i.code == "DATE_TOO_OLD" for i in issues)

    def test_five_years_plus_one_day(self):
        import datetime as dt

        date_val = TODAY - dt.timedelta(days=5 * 365 + 1)
        issues = check_date(date_val.isoformat(), today=TODAY)
        assert any(i.code == "DATE_TOO_OLD" for i in issues)


# ==========================================================================
# check_no_items / check_qty_invalid
# ==========================================================================


class TestItemChecks:
    def test_no_items_empty_list(self):
        issues = check_no_items([])
        assert any(i.code == "NO_ITEMS" for i in issues)

    def test_no_items_none(self):
        issues = check_no_items(None)
        assert any(i.code == "NO_ITEMS" for i in issues)

    def test_items_present(self):
        assert check_no_items([{"item_name_raw": "x"}]) == []

    def test_qty_zero_invalid(self):
        issues = check_qty_invalid([{"qty": 0}])
        assert any(i.code == "QTY_INVALID" for i in issues)

    def test_qty_negative_invalid(self):
        issues = check_qty_invalid([{"qty": -1}])
        assert any(i.code == "QTY_INVALID" for i in issues)

    def test_qty_valid(self):
        assert check_qty_invalid([{"qty": 1}]) == []

    def test_qty_null_invalid(self):
        issues = check_qty_invalid([{"qty": None}])
        assert any(i.code == "QTY_INVALID" for i in issues)


# ==========================================================================
# check_price_outlier
# ==========================================================================


class TestPriceOutlier:
    def test_no_stats_no_issue(self):
        items = [{"sku_id": "SKU001", "unit_price": 99999}]
        assert check_price_outlier(items, {}) == []

    def test_insufficient_history_no_issue(self):
        items = [{"sku_id": "SKU001", "unit_price": 99999}]
        stats = {"SKU001": {"median": 1000, "count": 4}}
        assert check_price_outlier(items, stats) == []

    def test_outlier_too_low(self):
        items = [{"sku_id": "SKU001", "unit_price": 100, "item_name_raw": "test"}]
        stats = {"SKU001": {"median": 1000, "count": 10}}
        issues = check_price_outlier(items, stats)
        assert any(i.code == "PRICE_OUTLIER" for i in issues)

    def test_outlier_too_high(self):
        items = [{"sku_id": "SKU001", "unit_price": 99999, "item_name_raw": "test"}]
        stats = {"SKU001": {"median": 1000, "count": 10}}
        issues = check_price_outlier(items, stats)
        assert any(i.code == "PRICE_OUTLIER" for i in issues)

    def test_in_range(self):
        items = [{"sku_id": "SKU001", "unit_price": 1000, "item_name_raw": "test"}]
        stats = {"SKU001": {"median": 1000, "count": 10}}
        assert check_price_outlier(items, stats) == []


# ==========================================================================
# Matching – normalize and match_item
# ==========================================================================

_CEMENT_CATALOG = [
    {"alias_norm": "smn 3r", "sku_id": "SMN001"},
    {"alias_norm": "semen 3 roda", "sku_id": "SMN001"},
    {"alias_norm": "semen tiga roda 50kg", "sku_id": "SMN001"},
    {"alias_norm": "semen tiga roda", "sku_id": "SMN001"},
    {"alias_norm": "pipa pvc 3 4", "sku_id": "PVC001"},
    {"alias_norm": "cat tembok 5kg", "sku_id": "CAT001"},
]


class TestNormalize:
    def test_lowercase(self):
        assert normalize("Semen TIGA") == "semen tiga"

    def test_strip_punctuation(self):
        # normalize strips and collapses; trailing spaces are stripped
        assert normalize("semen-tiga/roda!") == "semen tiga roda"

    def test_collapse_whitespace(self):
        assert normalize("  semen   tiga  ") == "semen tiga"

    def test_keep_digits(self):
        assert normalize("3/4 inch") == "3 4 inch"


class TestMatchItem:
    def test_exact_alias_returns_auto(self):
        result = match_item("SMN 3R", _CEMENT_CATALOG)
        assert result.sku_id == "SMN001"
        assert result.level == "auto"
        assert result.score == 100.0

    def test_variant_semen_3_roda(self):
        result = match_item("semen 3 roda 50 kg", _CEMENT_CATALOG)
        assert result.sku_id == "SMN001"
        assert result.level in ("auto", "suggest")

    def test_variant_semen_tiga_roda(self):
        result = match_item("Semen Tiga Roda 50kg", _CEMENT_CATALOG)
        assert result.sku_id == "SMN001"
        assert result.level in ("auto", "suggest")

    def test_clearly_different_returns_none(self):
        result = match_item("Besi Beton 10mm", _CEMENT_CATALOG)
        assert result.level == "none"
        assert result.sku_id is None

    def test_empty_name_returns_none(self):
        result = match_item("", _CEMENT_CATALOG)
        assert result.level == "none"

    def test_empty_catalog_returns_none(self):
        result = match_item("Semen Tiga Roda", [])
        assert result.level == "none"


# ==========================================================================
# Confidence scoring
# ==========================================================================


class TestConfidence:
    def test_clean_receipt_gives_100_confirmed(self):
        score, status = compute_confidence([], confidence_threshold=0.85)
        assert score == 1.0
        assert status == "confirmed"

    def test_hard_issue_needs_review(self):
        issues = [Issue(code="TOTAL_MISMATCH", severity="hard", message="x")]
        score, status = compute_confidence(issues, confidence_threshold=0.85)
        assert status == "needs_review"
        assert score == 0.5  # 1.0 - 0.50

    def test_total_mismatch_always_needs_review(self):
        """Even with no other issues, a hard issue forces needs_review."""
        issues = [Issue(code="TOTAL_MISMATCH", severity="hard", message="x")]
        _, status = compute_confidence(issues, confidence_threshold=0.0)
        assert status == "needs_review"

    def test_single_unmatched_item_needs_review(self):
        """Regression: one unmatched item scores exactly 0.85, which used to auto-confirm."""
        issues = [Issue(code="ITEM_UNMATCHED", severity="soft", message="x")]
        score, status = compute_confidence(issues, confidence_threshold=0.85)
        assert score == pytest.approx(0.85)
        assert status == "needs_review"

    def test_unmatched_forces_review_regardless_of_threshold(self):
        issues = [Issue(code="ITEM_UNMATCHED", severity="soft", message="x")]
        _, status = compute_confidence(issues, confidence_threshold=0.0)
        assert status == "needs_review"

    def test_other_minor_soft_issues_still_confirm(self):
        """Only unmatched items force review; a low match or outlier above threshold passes."""
        for code, expected in [("ITEM_LOW_MATCH", 0.95), ("PRICE_OUTLIER", 0.90)]:
            score, status = compute_confidence(
                [Issue(code=code, severity="soft", message="x")], confidence_threshold=0.85
            )
            assert score == pytest.approx(expected)
            assert status == "confirmed"

    def test_unmatched_items_cap(self):
        """3 unmatched items → 3 × 0.15 = 0.45 deducted, capped at 0.45."""
        issues = [
            Issue(code="ITEM_UNMATCHED", severity="soft", message=f"item {i}")
            for i in range(4)  # 4 items but cap is 0.45
        ]
        score, _ = compute_confidence(issues, confidence_threshold=0.0)
        assert score == pytest.approx(1.0 - 0.45)

    def test_low_match_cap(self):
        """5 low-match items → 5 × 0.05 = 0.25 but cap is 0.20."""
        issues = [
            Issue(code="ITEM_LOW_MATCH", severity="soft", message=f"item {i}")
            for i in range(5)
        ]
        score, _ = compute_confidence(issues, confidence_threshold=0.0)
        assert score == pytest.approx(1.0 - 0.20)

    def test_clamp_at_zero(self):
        """Multiple heavy deductions cannot push below 0."""
        issues = (
            [Issue(code="TOTAL_MISMATCH", severity="hard", message="x")]
            + [Issue(code="ITEM_UNMATCHED", severity="soft", message=f"item {i}") for i in range(5)]
            + [Issue(code="PRICE_OUTLIER", severity="soft", message="x")]
            + [Issue(code="DATE_TOO_OLD", severity="soft", message="x")]
        )
        score, status = compute_confidence(issues, confidence_threshold=0.85)
        assert score >= 0.0
        assert status == "needs_review"

    def test_soft_only_below_threshold_needs_review(self):
        """Soft issues that push score below threshold → needs_review."""
        issues = [
            Issue(code="DATE_TOO_OLD", severity="soft", message="x"),
            Issue(code="ITEM_UNMATCHED", severity="soft", message="x"),
        ]
        # 1.0 - 0.20 - 0.15 = 0.65 < 0.85 → needs_review
        score, status = compute_confidence(issues, confidence_threshold=0.85)
        assert score == pytest.approx(0.65)
        assert status == "needs_review"


# ==========================================================================
# Pipeline integration
# ==========================================================================


class TestPipeline:
    def test_clean_extraction_confirmed(self):
        extraction = {
            "date": TODAY.isoformat(),
            "customer": "Pak Budi",
            "items": [
                {
                    "item_name_raw": "SMN 3R",
                    "qty": 5,
                    "unit": "sak",
                    "unit_price": 70000,
                    "line_total": 350000,
                },
            ],
            "total": 350000,
        }
        result = validate_extraction(extraction, _CEMENT_CATALOG, today=TODAY)
        assert result.status == "confirmed"
        assert result.confidence == 1.0
        assert result.items_with_matches[0].sku_id == "SMN001"

    def test_unknown_item_goes_to_review_even_when_math_is_right(self):
        extraction = {
            "date": TODAY.isoformat(),
            "customer": None,
            "items": [
                {"item_name_raw": "PSR BTN", "qty": 6, "unit": "m3",
                 "unit_price": 345632, "line_total": 2073792},
            ],
            "total": 2073792,
        }
        result = validate_extraction(extraction, _CEMENT_CATALOG, today=TODAY)
        assert any(i.code == "ITEM_UNMATCHED" for i in result.issues)
        assert not any(i.severity == "hard" for i in result.issues)
        assert result.status == "needs_review"

    def test_total_mismatch_needs_review(self):
        extraction = {
            "date": TODAY.isoformat(),
            "customer": "x",
            "items": [{"item_name_raw": "SMN 3R", "qty": 1, "unit_price": 70000, "line_total": 70000}],
            "total": 99999,  # wrong
        }
        result = validate_extraction(extraction, _CEMENT_CATALOG, today=TODAY)
        assert result.status == "needs_review"
        assert any(i.code == "TOTAL_MISMATCH" for i in result.issues)
