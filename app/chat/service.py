"""app/chat/service.py – Text-to-SQL chat service."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.chat.prompts import SQL_SYSTEM_PROMPT, answer_prompt
from app.chat.sql_guard import UnsafeSQL, validate_sql
from app.llm import call_with_retry, completion_kwargs, make_client, message_text

logger = logging.getLogger(__name__)
MAX_QUESTION_LENGTH = 500


def chat(db: Session, question: str, lang: str = "id", with_answer: bool = True) -> dict[str, Any]:
    """Process a natural-language question and return the SQL, its rows and a written answer.

    `lang` ("id" or "en") is the language of the answer. Returns dict: {answer, sql, columns, rows}.
    With `with_answer=False` the answer is None and only the SQL and the rows are returned, so a
    caller can show them at once and ask for the wording afterwards with `phrase_answer`.
    The written answer is only a rewording of rows that are already in hand: if the model is slow
    or down it is None, and the call still succeeds.
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
            client,
            settings,
            question,
            error_feedback=f"SQL tidak valid: {e}. Perbaiki dan kembalikan hanya SQL SELECT.",
            previous_sql=sql_raw,
        )
        try:
            safe_sql = validate_sql(sql_raw)
        except UnsafeSQL as e2:
            raise ValueError(f"Generated SQL failed validation: {e2}") from e2

    # Step 3: execute
    columns, rows = _execute_sql(db, safe_sql)

    # Step 4: generate answer (optional polish: a failure here must not lose the result)
    answer = None
    if with_answer:
        answer = _phrase(client, settings, question, columns, rows, lang)

    return {
        "answer": answer,
        "sql": safe_sql,
        "columns": columns,
        "rows": rows,
    }


def phrase_answer(question: str, columns: list[str], rows: list[list], lang: str = "id"):
    """The written answer for rows that are already known, or None when the model cannot give one.

    Raises RuntimeError if LLM is not configured.
    """
    from app.config import get_settings

    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_api_key:
        raise RuntimeError("LLM_BASE_URL and LLM_API_KEY must be configured for chat.")
    return _phrase(make_client(settings), settings, question, columns, rows, lang)


def _phrase(client, settings, question, columns, rows, lang) -> str | None:
    try:
        return _generate_answer(client, settings, question, columns, rows, lang)
    except Exception as e:  # timeout, 429, 5xx, an unreadable reply: the rows are still good
        logger.warning("chat answer not generated (%s: %s)", type(e).__name__, e)
        return None


def _generate_sql(
    client,
    settings,
    question: str,
    error_feedback: str | None = None,
    previous_sql: str = "",
) -> str:
    messages = [{"role": "system", "content": SQL_SYSTEM_PROMPT}]
    if error_feedback and previous_sql.strip():
        # Show the model its own rejected SQL, so the feedback has something to point at.
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": previous_sql})
        messages.append({"role": "user", "content": error_feedback})
    elif error_feedback:
        # Nothing usable came back the first time (an empty assistant turn can be rejected).
        messages.append({"role": "user", "content": question + "\n\n" + error_feedback})
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
    client, settings, question: str, columns: list[str], rows: list[list], lang: str = "id"
) -> str:
    if lang == "en":
        data_str = f"Columns: {columns}\nData ({len(rows)} rows): {rows[:20]}"
        user_text = f"Question: {question}\n\n{data_str}"
    else:
        data_str = f"Kolom: {columns}\nData ({len(rows)} baris): {rows[:20]}"
        user_text = f"Pertanyaan: {question}\n\n{data_str}"
    messages = [
        {"role": "system", "content": answer_prompt(lang)},
        {"role": "user", "content": user_text},
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
        # Optional polish: ride out a 1 s concurrency limit, never sleep through a 60 s one
        max_retries=1,
        max_delay=5.0,
    )
    fallback = (
        "Could not generate an answer." if lang == "en" else "Tidak dapat menghasilkan jawaban."
    )
    return message_text(resp, "chat answer") or fallback
