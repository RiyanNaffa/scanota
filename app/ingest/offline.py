"""app/ingest/offline.py – Receipt photo ingestion.

Saves image to storage, runs extraction, validates, persists transaction.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repository import (
    create_transaction,
    get_catalog_aliases,
    get_price_stats,
)
from app.extraction.service import extract_and_validate


async def ingest_receipt_file(
    db: Session,
    image_bytes: bytes,
    original_filename: str,
) -> dict[str, Any]:
    """Store image and persist extracted transaction.

    The image is stored under STORAGE_DIR with a random filename (never the
    user-supplied name) to avoid path traversal and name collisions.
    """
    settings = get_settings()

    # Save image with random name
    ext = ".jpg"
    if original_filename.lower().endswith(".png"):
        ext = ".png"
    elif original_filename.lower().endswith(".webp"):
        ext = ".webp"

    os.makedirs(settings.storage_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    image_path = os.path.join(settings.storage_dir, filename)

    with open(image_path, "wb") as f:
        f.write(image_bytes)

    catalog = get_catalog_aliases(db)
    price_stats = get_price_stats(db)

    # Blocking network calls (OCR + LLM, with retry sleeps): keep them off the event loop.
    raw_dict, validation = await asyncio.to_thread(
        extract_and_validate, image_bytes, catalog, price_stats
    )

    tx_id = create_transaction(
        db,
        tx_date=raw_dict.get("date") or "1970-01-01",
        channel="offline",
        customer=raw_dict.get("customer"),
        total=int(raw_dict.get("total") or 0),
        source="scan",
        status=validation.status,
        confidence=validation.confidence,
        issues=validation.issues,
        receipt_image_path=image_path,
        raw_extraction=raw_dict,
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
            for iwm in validation.items_with_matches
        ],
    )

    return {
        "id": tx_id,
        "status": validation.status,
        "confidence": validation.confidence,
        "issues": [
            {"code": i.code, "severity": i.severity, "message": i.message}
            for i in validation.issues
        ],
        "image_path": filename,
    }
