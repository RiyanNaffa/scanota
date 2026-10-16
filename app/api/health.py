"""app/api/health.py – Liveness and DB check endpoint."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import check_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_status = "ok" if check_db() else "error"
    return HealthResponse(status="ok", db=db_status)
