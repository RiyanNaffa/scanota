"""tests/unit/test_chat_answer_split.py – The rows come back even when the model cannot word them.

/chat used to answer 500 when the last LLM call (putting the rows into words) timed out, after
the SQL had already run. The wording is now optional, and can be fetched separately.
"""

from __future__ import annotations

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.chat import service
from app.config import Settings
from app.main import create_app


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(_env_file=None, llm_base_url="http://llm.test/v1", llm_api_key="key")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(service, "make_client", lambda s: object())
    monkeypatch.setattr(service, "_generate_sql", lambda *a, **k: "SELECT 1 AS n")
    monkeypatch.setattr(service, "_execute_sql", lambda db, sql: (["n"], [[1]]))
    return settings


def _timeout():
    return openai.APITimeoutError(request=httpx.Request("POST", "http://llm.test/v1"))


def test_a_timed_out_answer_still_returns_the_sql_and_rows(configured, monkeypatch):
    def boom(*args, **kwargs):
        raise _timeout()

    monkeypatch.setattr(service, "_generate_answer", boom)

    result = service.chat(None, "berapa?", "id")

    assert result["answer"] is None
    assert result["columns"] == ["n"] and result["rows"] == [[1]]
    assert "SELECT 1" in result["sql"]


def test_without_answer_the_model_is_not_asked_to_word_it(configured, monkeypatch):
    asked = []
    monkeypatch.setattr(service, "_generate_answer", lambda *a, **k: asked.append(1) or "x")

    result = service.chat(None, "berapa?", "id", with_answer=False)

    assert result["answer"] is None and result["rows"] == [[1]]
    assert asked == []


def test_a_good_answer_is_returned_as_before(configured, monkeypatch):
    monkeypatch.setattr(service, "_generate_answer", lambda *a, **k: "Satu.")

    assert service.chat(None, "berapa?", "id")["answer"] == "Satu."


def test_phrase_answer_gives_none_instead_of_raising(configured, monkeypatch):
    def boom(*args, **kwargs):
        raise _timeout()

    monkeypatch.setattr(service, "_generate_answer", boom)

    assert service.phrase_answer("berapa?", ["n"], [[1]], "en") is None


def test_phrase_answer_needs_the_llm_to_be_configured(monkeypatch):
    unset = Settings(_env_file=None, llm_base_url="", llm_api_key="")
    monkeypatch.setattr("app.config.get_settings", lambda: unset)

    with pytest.raises(RuntimeError):
        service.phrase_answer("berapa?", ["n"], [[1]])


def test_the_answer_call_does_not_stall_the_caller(monkeypatch):
    """It is optional polish: one short retry at most, never a 60 s Retry-After wait."""
    seen = {}

    def fake_retry(fn, **kwargs):
        seen.update(kwargs)
        raise _timeout()

    monkeypatch.setattr(service, "call_with_retry", fake_retry)
    settings = Settings(_env_file=None)

    with pytest.raises(openai.APITimeoutError):
        service._generate_answer(object(), settings, "q", ["n"], [[1]])
    assert seen["max_retries"] == 1
    assert seen["max_delay"] <= 5.0


# ---- the endpoint ------------------------------------------------------------------------


def test_the_answer_endpoint_returns_null_when_the_model_fails(configured, monkeypatch):
    def boom(*args, **kwargs):
        raise _timeout()

    monkeypatch.setattr(service, "_generate_answer", boom)

    reply = TestClient(create_app()).post(
        "/chat/answer", json={"question": "berapa?", "columns": ["n"], "rows": [[1]], "lang": "id"}
    )

    assert reply.status_code == 200
    assert reply.json() == {"answer": None}


def test_the_answer_endpoint_returns_the_wording(configured, monkeypatch):
    monkeypatch.setattr(service, "_generate_answer", lambda *a, **k: "Ada satu.")

    reply = TestClient(create_app()).post(
        "/chat/answer", json={"question": "berapa?", "columns": ["n"], "rows": [[1]]}
    )

    assert reply.json() == {"answer": "Ada satu."}


def test_the_answer_endpoint_refuses_more_rows_than_the_sql_guard_allows(configured):
    reply = TestClient(create_app()).post(
        "/chat/answer", json={"question": "q", "columns": ["n"], "rows": [[i] for i in range(201)]}
    )

    assert reply.status_code == 422


def test_the_answer_endpoint_says_503_without_an_llm(monkeypatch):
    unset = Settings(_env_file=None, llm_base_url="", llm_api_key="")
    monkeypatch.setattr("app.config.get_settings", lambda: unset)

    reply = TestClient(create_app()).post(
        "/chat/answer", json={"question": "q", "columns": ["n"], "rows": [[1]]}
    )

    assert reply.status_code == 503
