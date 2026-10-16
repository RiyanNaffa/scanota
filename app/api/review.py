"""app/api/review.py – Review and confirm endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.repository import (
    confirm_transaction,
    get_catalog_aliases,
    get_price_stats,
    get_review_transactions,
    get_transaction_with_items,
)
from app.db.session import get_db
from app.validation.pipeline import validate_extraction

router = APIRouter(tags=["review"])


class ConfirmItem(BaseModel):
    item_name_raw: str
    sku_id: str | None = None
    qty: float
    unit: str | None = None
    unit_price: int
    line_total: int


class ConfirmBody(BaseModel):
    tx_date: str
    customer: str | None = None
    items: list[ConfirmItem]
    total: int
    save_aliases: bool = False
    force: bool = False


@router.get("/review")
def list_review(
    db: Annotated[Session, Depends(get_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return get_review_transactions(db, limit=limit, offset=offset)


@router.post("/review/{tx_id}/confirm")
def confirm(
    tx_id: int,
    body: ConfirmBody,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tx = get_transaction_with_items(db, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Re-validate the corrected data
    catalog = get_catalog_aliases(db)
    price_stats = get_price_stats(db)
    extraction = {
        "date": body.tx_date,
        "customer": body.customer,
        "items": [
            {
                "item_name_raw": item.item_name_raw,
                "qty": item.qty,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "sku_id": item.sku_id,  # preserve human correction
            }
            for item in body.items
        ],
        "total": body.total,
    }
    result = validate_extraction(extraction, catalog, price_stats)

    has_hard = any(i.severity == "hard" for i in result.issues)
    if has_hard and not body.force:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Hard validation issues remain. Set force=true to override.",
                "issues": [
                    {"code": i.code, "message": i.message}
                    for i in result.issues
                    if i.severity == "hard"
                ],
            },
        )

    items_for_db = [
        {
            "item_name_raw": item.item_name_raw,
            "sku_id": item.sku_id
            or next(
                (
                    m.sku_id
                    for m in result.items_with_matches
                    if m.item_name_raw == item.item_name_raw
                ),
                None,
            ),
            "qty": item.qty,
            "unit": item.unit,
            "unit_price": item.unit_price,
            "line_total": item.line_total,
            "match_score": None,
        }
        for item in body.items
    ]

    confirm_transaction(
        db,
        tx_id,
        items=items_for_db,
        tx_date=body.tx_date,
        customer=body.customer,
        total=body.total,
        issues=result.issues,
        confidence=result.confidence,
        save_aliases=body.save_aliases,
        force=body.force,
    )

    return {"id": tx_id, "status": "confirmed", "confidence": result.confidence}
