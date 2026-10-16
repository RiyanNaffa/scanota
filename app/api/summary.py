"""app/api/summary.py – KPI summary endpoint."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.repository import get_summary
from app.db.session import get_db

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
def summary(
    db: Annotated[Session, Depends(get_db)],
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    return get_summary(db, date_from=date_from, date_to=date_to)
