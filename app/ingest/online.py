"""app/ingest/online.py – Online order ingestion (webhook JSON and CSV).

Maps the webhook payload to the internal extraction format, runs validation,
and persists the result. Idempotent on external_ref.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from app.db.repository import (
    create_transaction,
    get_catalog_aliases,
    get_price_stats,
    get_transaction_by_external_ref,
)
from app.validation.pipeline import validate_extraction


def ingest_online_order(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Ingest a single online order webhook payload.

    Returns:
        dict with id, status, confidence, issues, duplicate (bool).
    """
    external_ref = payload.get("external_ref")

    # Idempotency check
    if external_ref:
        existing = get_transaction_by_external_ref(db, external_ref)
        if existing:
            return {
                "id": existing["id"],
                "status": existing["status"],
                "confidence": existing["confidence"],
                "issues": existing["issues"] or [],
                "duplicate": True,
            }

    # Build extraction dict in the same shape as offline extraction
    items = [
        {
            "item_name_raw": item.get("item_name", ""),
            "qty": item.get("qty"),
            "unit": item.get("unit"),
            "unit_price": item.get("unit_price"),
            "line_total": int(item.get("qty", 0)) * int(item.get("unit_price", 0)),
        }
        for item in payload.get("items", [])
    ]
    extraction = {
        "date": payload.get("date"),
        "customer": payload.get("customer"),
        "items": items,
        "total": payload.get("total"),
    }

    catalog = get_catalog_aliases(db)
    price_stats = get_price_stats(db)
    result = validate_extraction(extraction, catalog, price_stats)

    tx_id = create_transaction(
        db,
        tx_date=extraction["date"],
        channel="online",
        customer=extraction.get("customer"),
        total=int(extraction.get("total") or 0),
        source="webhook",
        status=result.status,
        confidence=result.confidence,
        issues=result.issues,
        external_ref=external_ref,
        raw_extraction=payload,
        items=[
            {
                "item_name_raw": iwm.item_name_raw,
                "sku_id": iwm.sku_id,
                "qty": iwm.qty,
                "unit": iwm.unit,
                "unit_price": iwm.unit_price,
                "line_total": iwm.line_total,
                "match_score": iwm.match_score,
            }
            for iwm in result.items_with_matches
        ],
    )
    return {
        "id": tx_id,
        "status": result.status,
        "confidence": result.confidence,
        "issues": [
            {"code": i.code, "severity": i.severity, "message": i.message} for i in result.issues
        ],
        "duplicate": False,
    }


def ingest_csv(db: Session, csv_content: str) -> list[dict[str, Any]]:
    """Ingest a CSV of online orders. One row per item; rows with same external_ref form one order.

    Returns a list of per-order results (including row-level parse errors).
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    orders: dict[str, dict] = {}
    parse_errors: list[dict] = []

    for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        try:
            ref = row["external_ref"].strip()
            if not ref:
                parse_errors.append({"row": row_num, "error": "missing external_ref"})
                continue

            if ref not in orders:
                orders[ref] = {
                    "external_ref": ref,
                    "date": row.get("date", "").strip(),
                    "customer": row.get("customer", "").strip() or None,
                    "items": [],
                }

            qty = float(row.get("qty", 0))
            unit_price = int(float(row.get("unit_price", 0)))
            orders[ref]["items"].append(
                {
                    "item_name": row.get("item_name", "").strip(),
                    "qty": qty,
                    "unit": row.get("unit", "").strip() or None,
                    "unit_price": unit_price,
                }
            )
        except (KeyError, ValueError, TypeError) as exc:
            parse_errors.append({"row": row_num, "error": str(exc)})

    results = []
    for ref, order in orders.items():
        # Compute total from items
        order["total"] = sum(
            int(float(item["qty"])) * int(item["unit_price"]) for item in order["items"]
        )
        try:
            r = ingest_online_order(db, order)
            r["external_ref"] = ref
            results.append(r)
        except Exception as exc:
            results.append({"external_ref": ref, "error": str(exc)})

    if parse_errors:
        results.append({"parse_errors": parse_errors})

    return results
