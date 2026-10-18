"""app/api/chat.py – Chat endpoint."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.chat.sql_guard import MAX_LIMIT
from app.db.session import get_ro_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    lang: Literal["id", "en"] = "id"  # language of the answer, set by the dashboard switch
    # False returns the SQL and the rows without the written answer (answer is null), which is
    # what takes the longest; ask for it afterwards with POST /chat/answer
    answer: bool = True


class AnswerRequest(BaseModel):
    """Rows a previous /chat call returned, to be put into words."""

    question: str = Field(max_length=500)
    columns: list[str] = Field(max_length=50)
    rows: list[list[Any]] = Field(max_length=MAX_LIMIT)  # the SQL guard caps results at this
    lang: Literal["id", "en"] = "id"


@router.post("")
def chat_endpoint(
    body: ChatRequest,
    db: Annotated[Session, Depends(get_ro_db)],
) -> dict[str, Any]:
    from app.chat.service import chat

    try:
        return chat(db, body.question, body.lang, with_answer=body.answer)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/answer")
def answer_endpoint(body: AnswerRequest) -> dict[str, str | None]:
    """The written answer for rows already shown. {"answer": null} when the model is slow or down."""
    from app.chat.service import phrase_answer

    try:
        return {"answer": phrase_answer(body.question, body.columns, body.rows, body.lang)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
