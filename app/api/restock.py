"""app/api/restock.py – Restock and forecast series endpoints."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.forecast.service import build_restock_list, get_forecast_series

router = APIRouter(prefix="/restock", tags=["restock"])


@router.get("")
def restock(
    db: Annotated[Session, Depends(get_db)],
    explain: str | None = None,
) -> list[dict[str, Any]]:
    items = build_restock_list(db)

    if explain == "llm":
        items = _llm_explain(items)

    return items


@router.get("/{sku_id}/series")
def forecast_series(
    sku_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    result = get_forecast_series(db, sku_id)
    if result is None:
        raise HTTPException(status_code=404, detail="SKU not found or no sales data")
    return result


def _llm_explain(items: list[dict]) -> list[dict]:
    """Optionally rephrase reasons via LLM. Falls back silently on error."""
    try:
        from openai import OpenAI

        from app.config import get_settings

        settings = get_settings()
        if not settings.llm_base_url or not settings.llm_api_key:
            return items

        client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        for item in items:
            try:
                resp = client.chat.completions.create(
                    model=settings.llm_model_text,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Kamu adalah asisten toko. Parafrase kalimat berikut "
                                "menjadi lebih ramah dalam bahasa Indonesia. "
                                "Jangan ubah angka apapun. Hanya kembalikan kalimat, tanpa penjelasan."
                            ),
                        },
                        {"role": "user", "content": item["reason"]},
                    ],
                    temperature=0.3,
                    timeout=15,
                )
                item["reason"] = resp.choices[0].message.content.strip()
            except Exception:
                pass
    except Exception:
        pass
    return items
