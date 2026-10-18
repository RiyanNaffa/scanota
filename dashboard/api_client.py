"""dashboard/api_client.py – HTTP client for the scanota API."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
_TIMEOUT = 30
# Calls that wait on the LLM. Worst case for a receipt: OCR 60 s + main vision model 120 s +
# fallback model 120 s, and a 429 may also sit out a 60 s Retry-After. Usually it takes seconds.
_LLM_TIMEOUT = 300


def _error(e: httpx.HTTPError) -> dict:
    """{"error": ...} for a failed call, using the API's own `detail` message when it sent one."""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            detail = e.response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, str) and detail:
            return {"error": detail}
    return {"error": str(e) or type(e).__name__}


def _get(path: str, params: dict | None = None, timeout: float = _TIMEOUT) -> Any:
    try:
        r = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        return _error(e)


def _post(
    path: str, json: dict | None = None, files=None, data=None, timeout: float = _TIMEOUT
) -> Any:
    try:
        r = httpx.post(f"{API_BASE_URL}{path}", json=json, files=files, data=data, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        return _error(e)


def health() -> dict:
    """Reachability for the sidebar. The API holds the CPU while it computes a forecast, so a
    health check that times out means "up but busy", not "offline"; only a refused or failed
    connection is reported as an error."""
    try:
        r = httpx.get(f"{API_BASE_URL}/health", timeout=2)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        return {"status": "ok", "busy": True}
    except httpx.HTTPError as e:
        return _error(e)


def summary(date_from=None, date_to=None) -> dict:
    params = {}
    if date_from:
        params["date_from"] = str(date_from)
    if date_to:
        params["date_to"] = str(date_to)
    return _get("/summary", params=params)


def transactions(channel=None, status=None, date_from=None, date_to=None, limit=100, offset=0):
    params = {"limit": limit, "offset": offset}
    if channel:
        params["channel"] = channel
    if status:
        params["status"] = status
    if date_from:
        params["date_from"] = str(date_from)
    if date_to:
        params["date_to"] = str(date_to)
    return _get("/transactions", params=params)


def transaction_detail(tx_id: int) -> dict:
    return _get(f"/transactions/{tx_id}")


def review_list(limit=100) -> list:
    return _get("/review", params={"limit": limit}) or []


def confirm_transaction(tx_id: int, body: dict) -> dict:
    return _post(f"/review/{tx_id}/confirm", json=body)


def products() -> list:
    return _get("/products") or []


def update_stock(sku_id: str, current_stock: float) -> dict:
    return _post(f"/products/{sku_id}/stock", json={"current_stock": current_stock})


def restock(explain: str | None = None, lang: str = "id") -> list:
    params = {"lang": lang}
    if explain:
        params["explain"] = explain
    return _get("/restock", params=params, timeout=_LLM_TIMEOUT if explain else _TIMEOUT) or []


def forecast_series(sku_id: str) -> dict:
    return _get(f"/restock/{sku_id}/series")


def chat(question: str, lang: str = "id") -> dict:
    return _post("/chat", json={"question": question, "lang": lang}, timeout=_LLM_TIMEOUT)


def receipt_image(tx_id: int) -> bytes | None:
    """The stored photo of a scanned receipt, or None when there is none."""
    try:
        r = httpx.get(f"{API_BASE_URL}/transactions/receipts/{tx_id}/image", timeout=_TIMEOUT)
    except httpx.HTTPError:
        return None
    return r.content if r.status_code == 200 else None


def ingest_receipt(file_bytes: bytes, filename: str, content_type: str) -> dict:
    return _post(
        "/ingest/receipt",
        files={"file": (filename, file_bytes, content_type)},
        timeout=_LLM_TIMEOUT,
    )
