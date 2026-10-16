"""app/api/products.py – Product master endpoints."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.repository import get_product, get_products, update_stock
from app.db.session import get_db

router = APIRouter(prefix="/products", tags=["products"])


class StockUpdate(BaseModel):
    current_stock: float


@router.get("")
def list_products(db: Annotated[Session, Depends(get_db)]) -> list[dict[str, Any]]:
    return get_products(db)


@router.put("/{sku_id}/stock")
def set_stock(
    sku_id: str,
    body: StockUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    product = get_product(db, sku_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    update_stock(db, sku_id, Decimal(str(body.current_stock)))
    return {"sku_id": sku_id, "current_stock": body.current_stock}
