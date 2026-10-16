"""app/chat/service.py – Text-to-SQL chat service."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.chat.prompts import ANSWER_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT
from app.chat.sql_guard import UnsafeSQL, validate_sql
from app.llm import call_with_retry, completion_kwargs, make_client, message_text

logger = logging.getLogger(__name__)
MAX_QUESTION_LENGTH = 500


def chat(db: Session, question: str) -> dict[str, Any]:
    """Process a natural-language question and return an answer with supporting SQL.

    Returns dict: {answer, sql, columns, rows}
    Raises ValueError on input errors.
    Raises RuntimeError if LLM is not configured.
    """
    from app.config import get_settings

    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        raise RuntimeError("LLM_BASE_URL and LLM_API_KEY must be configured for chat.")

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question too long (max {MAX_QUESTION_LENGTH} characters).")

    client = make_client(settings)

    # Step 1: question → SQL
    sql_raw = _generate_sql(client, settings, question)

    # Step 2: validate and sanitize
    try:
        safe_sql = validate_sql(sql_raw)
    except UnsafeSQL as e:
        # Retry with error feedback
        sql_raw = _generate_sql(
            client, settings, question,
            error_feedback=f"SQL tidak valid: {e}. Perbaiki dan kembalikan hanya SQL SELECT."
        )
        try:
            safe_sql = validate_sql(sql_raw)
        except UnsafeSQL as e2:
            raise ValueError(f"Generated SQL failed validation: {e2}") from e2

    # Step 3: execute
    columns, rows = _execute_sql(db, safe_sql)

    # Step 4: generate answer
    answer = _generate_answer(client, settings, question, columns, rows)

    return {
        "answer": answer,
        "sql": safe_sql,
        "columns": columns,
        "rows": rows,
    }


def _generate_sql(client, settings, question: str, error_feedback: str | None = None) -> str:
    messages = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]
    if error_feedback:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": ""})
        messages.append({"role": "user", "content": error_feedback})
    else:
        messages.append({"role": "user", "content": question})

    # SQL correctness needs real reasoning, so this call gets the larger effort and budget.
    resp = call_with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm_model_text,
            messages=messages,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
            **completion_kwargs(settings.llm_reasoning_effort_sql, settings.llm_max_tokens_sql),
        ),
        settings=settings,
    )
    return message_text(resp, "SQL generation")


def _execute_sql(db: Session, sql: str) -> tuple[list[str], list[list]]:
    from sqlalchemy import text

    try:
        result = db.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
        # Serialize non-JSON-friendly types
        for row in rows:
            for i, val in enumerate(row):
                if hasattr(val, "isoformat"):
                    row[i] = val.isoformat()
                elif hasattr(val, "__float__"):
                    try:
                        row[i] = float(val)
                    except Exception:
                        row[i] = str(val)
        return columns, rows
    except Exception as e:
        raise ValueError(f"SQL execution error: {e}") from e


def _generate_answer(
    client, settings, question: str, columns: list[str], rows: list[list]
) -> str:
    data_str = f"Kolom: {columns}\nData ({len(rows)} baris): {rows[:20]}"
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Pertanyaan: {question}\n\n{data_str}"},
    ]
    # The data is already computed by SQL; this only phrases it, so light reasoning is enough.
    resp = call_with_retry(
        lambda: client.chat.completions.create(
            model=settings.llm_model_text,
            messages=messages,
            temperature=0.2,
            timeout=30,
            **completion_kwargs(settings.llm_reasoning_effort_text, settings.llm_max_tokens_answer),
        ),
        settings=settings,
    )
    return message_text(resp, "chat answer") or "Tidak dapat menghasilkan jawaban."
