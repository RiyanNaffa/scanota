"""app/api/evolus.py – Evolus stats endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/evolus", tags=["evolus"])


@router.get("/stats")
def evolus_stats() -> dict:
    """Return Evolus API call counts (no secrets)."""
    try:
        from app.evolus.client import EvolusClient

        client = EvolusClient()
        return {"stats": client.get_stats()}
    except Exception:
        return {"stats": {}}
