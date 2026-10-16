"""app/api/ingest.py – Ingest endpoints: online webhook, CSV, receipt."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.extraction.client import ExtractionError
from app.ingest.online import ingest_csv, ingest_online_order

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

EXTRACTION_UNAVAILABLE = (
    "Model pembaca nota sedang sibuk atau tidak merespons. Tunggu sebentar lalu coba lagi."
)


class OnlineOrderItem(BaseModel):
    item_name: str
    qty: float
    unit: str | None = None
    unit_price: int


class OnlineOrderPayload(BaseModel):
    external_ref: str
    date: str
    customer: str | None = None
    items: list[OnlineOrderItem]
    total: int


@router.post("/online")
def ingest_online(
    payload: OnlineOrderPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    result = ingest_online_order(db, payload.model_dump())
    return result


@router.post("/online/csv")
async def ingest_online_csv(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=415, detail="Only .csv files are accepted")
    content = await file.read()
    csv_text = content.decode("utf-8-sig")  # handle BOM
    return ingest_csv(db, csv_text)


@router.post("/receipt")
async def ingest_receipt(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Ingest a receipt image. Requires LLM configuration."""
    from app.config import get_settings
    from app.ingest.offline import ingest_receipt_file

    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        raise HTTPException(
            status_code=503,
            detail="LLM_BASE_URL and LLM_API_KEY must be configured to use receipt scanning.",
        )

    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{file.content_type}'. Accept: jpeg, png, webp.",
        )

    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum {settings.max_upload_mb} MB.",
        )

    try:
        return await ingest_receipt_file(db, data, file.filename or "receipt")
    except ExtractionError as exc:
        # Provider errors can carry internal details; log them, show the user a plain message.
        logger.warning("Receipt extraction failed: %s", exc)
        raise HTTPException(status_code=502, detail=EXTRACTION_UNAVAILABLE) from exc
