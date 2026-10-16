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
        import openai

        from app.config import get_settings
        from app.llm import call_with_retry, completion_kwargs, make_client, message_text

        settings = get_settings()
        if not settings.llm_base_url or not settings.llm_api_key:
            return items

        client = make_client(settings)
        for item in items:
            try:
                # Plain rephrasing of a sentence: light reasoning and a small budget.
                resp = call_with_retry(
                    lambda item=item: client.chat.completions.create(
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
                        **completion_kwargs(
                            settings.llm_reasoning_effort_text, settings.llm_max_tokens_explain
                        ),
                    ),
                    settings=settings,
                    # Optional polish, one call per item: ride out a 1 s concurrency limit but
                    # never sleep through a 60 s per-minute limit (Tokenfactory allows ~20 RPM).
                    max_retries=1,
                    max_delay=5.0,
                )
                item["reason"] = message_text(resp, "restock rephrase") or item["reason"]
            except openai.RateLimitError:
                # Rate limited: stop here and keep the original reasons for the rest.
                break
            except Exception:
                pass
    except Exception:
        pass
    return items
