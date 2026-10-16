"""app/api/transactions.py – Transaction list and detail endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.repository import get_transaction_with_items, list_transactions
from app.db.session import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def get_transactions(
    db: Annotated[Session, Depends(get_db)],
    channel: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return list_transactions(
        db,
        channel=channel,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=min(limit, 500),
        offset=offset,
    )


@router.get("/{tx_id}")
def get_transaction(
    tx_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tx = get_transaction_with_items(db, tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.get("/receipts/{tx_id}/image")
def get_receipt_image(tx_id: int, db: Annotated[Session, Depends(get_db)]) -> FileResponse:
    tx = get_transaction_with_items(db, tx_id)
    if not tx or not tx.get("receipt_image_path"):
        raise HTTPException(status_code=404, detail="Receipt image not found")
    return FileResponse(tx["receipt_image_path"])
