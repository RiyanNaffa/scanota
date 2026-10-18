"""tests/unit/test_ocr_eval.py – Scoring of the receipt-reading evaluation (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.eval.ocr_eval import (
    evaluate,
    f1,
    format_report,
    load_truth,
    match_items,
    normalise,
    score_receipt,
    summarise,
)


def _truth(**over):
    base = {
        "filename": "receipt_0001.png",
        "date": "2025-11-06",
        "total": 134784,
        "true_total": 134784,
        "intentional_error": False,
        "items": [
            {
                "item_name": "s gresik",
                "sku_id": "SMN002",
                "qty": 2.0,
                "unit": "sak",
                "unit_price": 67392,
                "line_total": 134784,
            }
        ],
    }
    base.update(over)
    return base


def _extraction(**over):
    base = {
        "date": "2025-11-06",
        "total": 134784,
        "items": [{"item_name_raw": "S Gresik.", "qty": 2, "line_total": 134784}],
    }
    base.update(over)
    return base


def _validation(sku="SMN002", codes=(), status="confirmed"):
    return SimpleNamespace(
        issues=[SimpleNamespace(code=c) for c in codes],
        items_with_matches=[SimpleNamespace(sku_id=sku)],
        status=status,
    )


def test_normalise_ignores_case_punctuation_and_spacing():
    assert normalise("  SMN   3R. ") == normalise("smn 3r") == "smn 3r"


def test_f1():
    assert f1(0, 5, 5) == 0.0
    assert f1(10, 0, 0) == 1.0
    assert f1(3, 1, 1) == pytest.approx(0.75)


def test_match_items_strict_and_loose():
    truth = _truth()["items"]
    exact = match_items([{"item_name_raw": "s gresik", "qty": 2, "line_total": 134784}], truth)
    wrong_total = match_items([{"item_name_raw": "S GRESIK", "qty": 2, "line_total": 13478}], truth)
    wrong_name = match_items([{"item_name_raw": "semen", "qty": 2, "line_total": 134784}], truth)

    assert (exact["strict_tp"], exact["loose_tp"]) == (1, 1)
    assert (wrong_total["strict_tp"], wrong_total["loose_tp"]) == (0, 1)  # right name, wrong number
    assert (wrong_name["strict_tp"], wrong_name["loose_tp"]) == (0, 0)


def test_one_truth_item_is_matched_only_once():
    twice = [{"item_name_raw": "s gresik", "qty": 2, "line_total": 134784}] * 2
    assert match_items(twice, _truth()["items"])["strict_tp"] == 1


def test_perfect_receipt():
    s = score_receipt(_extraction(), _validation(), _truth())
    assert s["date_ok"] and s["total_ok"] and s["sku_ok"] and not s["failed"]
    assert s["items"]["strict_tp"] == 1


def test_failed_call_scores_zero_everywhere():
    s = score_receipt(None, None, _truth())
    assert s["failed"] and not s["date_ok"] and not s["total_ok"] and not s["sku_ok"]


def test_wrong_printed_total_is_expected_as_printed():
    truth = _truth(total=86523, true_total=84263, intentional_error=True)
    printed = score_receipt(
        _extraction(total=86523),
        _validation(codes=["TOTAL_MISMATCH"], status="needs_review"),
        truth,
    )
    corrected = score_receipt(_extraction(total=84263), _validation(), truth)

    assert printed["total_ok"] and printed["flagged_total_mismatch"] and printed["needs_review"]
    assert not corrected["total_ok"]  # the model "fixed" the total instead of copying it


def test_summary_counts_caught_errors_and_false_alarms():
    scores = [
        score_receipt(_extraction(), _validation(), _truth()),
        score_receipt(  # clean receipt wrongly flagged
            _extraction(), _validation(codes=["TOTAL_MISMATCH"], status="needs_review"), _truth()
        ),
        score_receipt(  # wrong printed total, caught
            _extraction(total=9),
            _validation(codes=["TOTAL_MISMATCH"], status="needs_review"),
            _truth(total=9, true_total=8, intentional_error=True),
        ),
        score_receipt(  # wrong printed total, missed
            _extraction(total=9),
            _validation(),
            _truth(total=9, true_total=8, intentional_error=True),
        ),
    ]

    s = summarise(scores)

    assert s["receipts"] == 4 and s["wrong_totals"] == 2 and s["clean_receipts"] == 2
    assert s["wrong_totals_caught"] == 1
    assert s["clean_flagged_by_mistake"] == 1
    assert s["field_accuracy"] == 1.0
    assert s["item_f1"] == 1.0


def test_evaluate_runs_every_receipt_and_reports_progress():
    seen = []

    summary, scores = evaluate(
        [_truth(), _truth(filename="b.png")],
        lambda t: (_extraction(), _validation()),
        progress=lambda i, n, s: seen.append((i, n, s["file"])),
    )

    assert summary["receipts"] == 2 and len(scores) == 2
    assert seen == [(1, 2, "receipt_0001.png"), (2, 2, "b.png")]


def test_report_mentions_both_passes():
    s = summarise([score_receipt(_extraction(), _validation(), _truth())])
    text = format_report(
        s, s, {"receipts": 1, "ocr_available": 1, "fallback_used": 0, "seconds": 3}
    )

    assert "with OCR hint" in text and "vision only" in text and "Item F1" in text


def test_sample_ground_truth_is_what_the_scoring_expects():
    truths = load_truth()

    assert len(truths) == 40
    assert sum(t["intentional_error"] for t in truths) == 5
    assert all(len(t["items"]) >= 1 and {"date", "total", "filename"} <= set(t) for t in truths)


def test_concurrent_workers_keep_the_receipt_order():
    import time

    truths = [_truth(filename=f"r{i}.png") for i in range(6)]

    def slow_first(truth):
        if truth["filename"] == "r0.png":
            time.sleep(0.05)  # finishes last, must still be reported first
        return _extraction(), _validation()

    order = []
    summary, scores = evaluate(
        truths, slow_first, progress=lambda i, n, s: order.append(s["file"]), workers=3
    )

    assert [s["file"] for s in scores] == [f"r{i}.png" for i in range(6)]
    assert order == [f"r{i}.png" for i in range(6)]
    assert summary["receipts"] == 6


def test_failed_reads_are_retried_so_an_outage_is_not_scored_as_a_misread():
    calls = {"r1.png": 0}

    def flaky(truth):
        calls[truth["filename"]] = calls.get(truth["filename"], 0) + 1
        if truth["filename"] == "r1.png" and calls["r1.png"] == 1:
            return None, None  # first try hits a timeout
        return _extraction(), _validation()

    summary, scores = evaluate(
        [_truth(filename="r0.png"), _truth(filename="r1.png")], flaky, retry_failed=1
    )

    assert summary["failed_calls"] == 0 and summary["date_accuracy"] == 1.0
    assert calls == {"r0.png": 1, "r1.png": 2}  # only the failed receipt was read again


def test_a_receipt_that_keeps_failing_counts_as_a_failed_call():
    def always_down(truth):
        return None, None

    summary, _ = evaluate([_truth()], always_down, retry_failed=2)

    assert summary["failed_calls"] == 1 and summary["date_accuracy"] == 0.0
