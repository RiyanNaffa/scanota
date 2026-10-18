"""app/api/chat.py – Chat endpoint."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_ro_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    lang: Literal["id", "en"] = "id"  # language of the answer, set by the dashboard switch


@router.post("")
def chat_endpoint(
    body: ChatRequest,
    db: Annotated[Session, Depends(get_ro_db)],
) -> dict[str, Any]:
    from app.chat.service import chat

    try:
        return chat(db, body.question, body.lang)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
