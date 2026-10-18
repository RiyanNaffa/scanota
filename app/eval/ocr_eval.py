"""app/eval/ocr_eval.py – Score receipt reading against the ground truth of the sample receipts.

Run (needs the stack up, the seed loaded and a live LLM endpoint):  make eval
    docker compose exec api python -m app.eval.ocr_eval [--limit N] [--json out.json]

Every receipt in data/sample_receipts goes through the production steps: preprocess, OCR hint,
vision extraction, validation. It is read twice, with and without the OCR hint, so the numbers
also say whether the OCR endpoint earns its extra request.

Scores:
- date / total: exact match. The expected total is the one PRINTED on the receipt, because five
  receipts carry a wrong total on purpose and the model is told to copy what is written.
- item F1: an extracted item counts when its normalised name, quantity and line total all match;
  the name-only F1 is reported next to it to separate misread names from misread numbers.
- SKU: the validation step matched the item to the right product.
- errors caught: of the receipts with a wrong printed total, how many ended up flagged for review
  with TOTAL_MISMATCH, and how many correct receipts were flagged by mistake.

The sample receipts are synthetic renders (one item each), so this measures the pipeline on clean,
printed text. Handwriting and crumpled paper are not covered.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

DATA_DIR = os.path.join("data", "sample_receipts")


def normalise(name: Any) -> str:
    """Lower-case, strip punctuation and collapse spaces, so 'SMN  3R.' equals 'smn 3r'."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(name or "").lower())).strip()


def _same_number(a: Any, b: Any) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def f1(tp: int, fp: int, fn: int) -> float:
    if tp == 0:
        return 0.0
    precision, recall = tp / (tp + fp), tp / (tp + fn)
    return 2 * precision * recall / (precision + recall)


def match_items(extracted: list[dict], truth: list[dict]) -> dict[str, int]:
    """Greedy one-to-one matching; returns true/false positives and false negatives.

    strict = name + quantity + line total, loose = name only.
    """
    counts = {"strict_tp": 0, "loose_tp": 0, "n_extracted": len(extracted), "n_truth": len(truth)}
    left = list(truth)
    for item in extracted:
        name = normalise(item.get("item_name_raw"))
        for t in left:
            if normalise(t["item_name"]) != name:
                continue
            counts["loose_tp"] += 1
            if _same_number(item.get("qty"), t["qty"]) and _same_number(
                item.get("line_total"), t["line_total"]
            ):
                counts["strict_tp"] += 1
            left.remove(t)
            break
    return counts


def score_receipt(
    extraction: dict | None, validation: Any | None, truth: dict[str, Any]
) -> dict[str, Any]:
    """Score one receipt. extraction/validation are None when the model call failed."""
    ex = extraction or {}
    issues = {i.code for i in getattr(validation, "issues", [])}
    matches = getattr(validation, "items_with_matches", []) or []
    sku_ok = (
        bool(matches)
        and len(truth["items"]) == 1
        and (matches[0].sku_id == truth["items"][0]["sku_id"])
    )
    return {
        "file": truth["filename"],
        "failed": extraction is None,
        "date_ok": ex.get("date") == truth["date"],
        "total_ok": _same_number(ex.get("total"), truth["total"]),
        "items": match_items(ex.get("items") or [], truth["items"]),
        "sku_ok": sku_ok,
        "wrong_printed_total": bool(truth["intentional_error"]),
        "flagged_total_mismatch": "TOTAL_MISMATCH" in issues,
        "needs_review": getattr(validation, "status", "") == "needs_review",
    }


def summarise(scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-receipt scores into the numbers reported in the README."""
    n = len(scores) or 1
    strict = sum(s["items"]["strict_tp"] for s in scores)
    loose = sum(s["items"]["loose_tp"] for s in scores)
    extracted = sum(s["items"]["n_extracted"] for s in scores)
    truth = sum(s["items"]["n_truth"] for s in scores)
    wrong = [s for s in scores if s["wrong_printed_total"]]
    clean = [s for s in scores if not s["wrong_printed_total"]]
    return {
        "receipts": len(scores),
        "failed_calls": sum(s["failed"] for s in scores),
        "date_accuracy": sum(s["date_ok"] for s in scores) / n,
        "total_accuracy": sum(s["total_ok"] for s in scores) / n,
        "field_accuracy": sum(s["date_ok"] and s["total_ok"] for s in scores) / n,
        "item_f1": f1(strict, extracted - strict, truth - strict),
        "item_name_f1": f1(loose, extracted - loose, truth - loose),
        "sku_accuracy": sum(s["sku_ok"] for s in scores) / n,
        "wrong_totals": len(wrong),
        "wrong_totals_caught": sum(
            s["flagged_total_mismatch"] and s["needs_review"] for s in wrong
        ),
        "clean_receipts": len(clean),
        "clean_flagged_by_mistake": sum(s["flagged_total_mismatch"] for s in clean),
        "needs_review_rate": sum(s["needs_review"] for s in scores) / n,
    }


def load_truth(data_dir: str = DATA_DIR) -> list[dict[str, Any]]:
    with open(os.path.join(data_dir, "ground_truth.json"), encoding="utf-8") as f:
        return json.load(f)


def evaluate(
    truths: list[dict[str, Any]],
    read: Callable[[dict[str, Any]], tuple[dict | None, Any | None]],
    progress: Callable[[int, int, dict[str, Any]], None] | None = None,
    workers: int = 1,
    retry_failed: int = 1,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run `read(truth)` -> (extraction dict or None, validation) on each receipt and score it.

    With workers > 1 receipts are read concurrently (results stay in order). Tokenfactory allows 8
    concurrent requests and about 20 per minute for a team key, so 3 workers is a safe speed-up.
    A read that failed (timeout, rate limit) says nothing about accuracy, so failed receipts are
    read again, one at a time, up to `retry_failed` times; whatever still fails is reported as a
    failed call and scores zero.
    """
    results: list[tuple[dict | None, Any | None]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, (truth, result) in enumerate(zip(truths, pool.map(read, truths), strict=True), 1):
            results.append(result)
            if progress:
                progress(i, len(truths), score_receipt(*result, truth))
    for _ in range(retry_failed):
        for i, truth in enumerate(truths):
            if results[i][0] is None:
                results[i] = read(truth)
    scores = [score_receipt(*result, truth) for truth, result in zip(truths, results, strict=True)]
    return summarise(scores), scores


def format_report(with_ocr: dict[str, Any], vision_only: dict[str, Any] | None, extra: dict) -> str:
    def pct(x: float) -> str:
        return f"{x:.1%}"

    rows = [
        ("Date correct", "date_accuracy", pct),
        ("Total correct (as printed)", "total_accuracy", pct),
        ("Date and total both correct", "field_accuracy", pct),
        ("Item F1 (name + qty + line total)", "item_f1", lambda x: f"{x:.3f}"),
        ("Item F1 (name only)", "item_name_f1", lambda x: f"{x:.3f}"),
        ("Matched to the right SKU", "sku_accuracy", pct),
        ("Sent to review", "needs_review_rate", pct),
    ]
    head = f"{'':<36}{'with OCR hint':>15}" + (f"{'vision only':>13}" if vision_only else "")
    lines = [f"OCR evaluation: {with_ocr['receipts']} sample receipts", "", head]
    for label, key, fmt in rows:
        line = f"{label:<36}{fmt(with_ocr[key]):>15}"
        if vision_only:
            line += f"{fmt(vision_only[key]):>13}"
        lines.append(line)
    for title, s in (("with OCR hint", with_ocr), ("vision only", vision_only)):
        if not s:
            continue
        lines.append(
            f"Wrong printed totals caught ({title}): {s['wrong_totals_caught']} of {s['wrong_totals']}; "
            f"correct receipts flagged by mistake: {s['clean_flagged_by_mistake']} of {s['clean_receipts']}; "
            f"failed calls: {s['failed_calls']}"
        )
    lines.append(
        f"OCR text available for {extra['ocr_available']} of {extra['receipts']} receipts; "
        f"fallback model used for {extra['fallback_used']} reads; took {extra['seconds']:.0f} s"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, help="only the first N receipts (cheaper trial run)")
    parser.add_argument("--no-ablation", action="store_true", help="skip the vision-only pass")
    parser.add_argument("--workers", type=int, default=3, help="receipts read at once (default 3)")
    parser.add_argument(
        "--retry-failed", type=int, default=1, help="extra tries for receipts whose call failed"
    )
    parser.add_argument("--json", help="also write the raw scores to this path")
    args = parser.parse_args()

    from app.db.repository import get_catalog_aliases, get_price_stats
    from app.db.session import SessionLocal
    from app.extraction.client import ExtractionClient, ExtractionError
    from app.extraction.ocr import OcrClient
    from app.extraction.preprocess import preprocess_image
    from app.validation.pipeline import validate_extraction

    truths = load_truth()[: args.limit]
    db = SessionLocal()
    try:
        catalog, price_stats = get_catalog_aliases(db), get_price_stats(db)
    finally:
        db.close()

    ocr = OcrClient()
    images: dict[str, bytes] = {}
    ocr_texts: dict[str, str | None] = {}
    stats = {"ocr_available": 0, "fallback_used": 0}
    lock = threading.Lock()

    def image_of(truth: dict[str, Any]) -> bytes:
        name = truth["filename"]
        if name not in images:
            with open(os.path.join(DATA_DIR, name), "rb") as f:
                images[name] = preprocess_image(f.read())
        return images[name]

    def ocr_text_of(truth: dict[str, Any]) -> str | None:
        """OCR once per receipt (it is billed per page); only the pass that uses it asks."""
        name = truth["filename"]
        if name not in ocr_texts:
            text = ocr.read(image_of(truth))
            with lock:
                ocr_texts[name] = text
                stats["ocr_available"] += text is not None
        return ocr_texts[name]

    def reader(use_ocr: bool):
        def read(truth: dict[str, Any]):
            image = image_of(truth)
            text = ocr_text_of(truth) if use_ocr else None
            client = ExtractionClient()  # fresh client: the fallback switch is per receipt
            try:
                result = client.extract(image, ocr_text=text)
            except ExtractionError as exc:
                print(f"  {truth['filename']}: extraction failed: {str(exc)[:120]}")
                return None, None
            if client._on_fallback:
                with lock:
                    stats["fallback_used"] += 1
            raw = result.to_extraction_dict()
            return raw, validate_extraction(raw, catalog, price_stats)

        return read

    def progress(i: int, n: int, s: dict[str, Any]) -> None:
        mark = "ok " if s["date_ok"] and s["total_ok"] else "BAD"
        print(f"  [{i:>2}/{n}] {s['file']} {mark}", flush=True)

    started = time.time()
    print("Pass 1: OCR hint + vision model")
    with_ocr, scores_a = evaluate(truths, reader(True), progress, args.workers, args.retry_failed)
    vision_only = scores_b = None
    if not args.no_ablation:
        print("Pass 2: vision model only")
        vision_only, scores_b = evaluate(
            truths, reader(False), progress, args.workers, args.retry_failed
        )

    extra = {"receipts": len(truths), "seconds": time.time() - started, **stats}
    print()
    print(format_report(with_ocr, vision_only, extra))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "with_ocr": with_ocr,
                    "vision_only": vision_only,
                    "extra": extra,
                    "scores_with_ocr": scores_a,
                    "scores_vision_only": scores_b,
                },
                f,
                indent=2,
                default=str,
            )


if __name__ == "__main__":
    main()
