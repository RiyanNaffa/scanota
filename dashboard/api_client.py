"""dashboard/api_client.py – HTTP client for the scanota API."""
from __future__ import annotations

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
_TIMEOUT = 30


def _get(path: str, params: dict | None = None) -> Any:
    try:
        r = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}


def _post(path: str, json: dict | None = None, files=None, data=None) -> Any:
    try:
        r = httpx.post(
            f"{API_BASE_URL}{path}", json=json, files=files, data=data, timeout=_TIMEOUT
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}


def health() -> dict:
    return _get("/health")


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


def restock(explain: str | None = None) -> list:
    params = {}
    if explain:
        params["explain"] = explain
    return _get("/restock", params=params) or []


def forecast_series(sku_id: str) -> dict:
    return _get(f"/restock/{sku_id}/series")


def chat(question: str) -> dict:
    return _post("/chat", json={"question": question})


def ingest_receipt(file_bytes: bytes, filename: str, content_type: str) -> dict:
    return _post(
        "/ingest/receipt",
        files={"file": (filename, file_bytes, content_type)},
    )
