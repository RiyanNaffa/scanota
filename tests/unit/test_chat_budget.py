"""tests/unit/test_chat_budget.py – Chat calls carry the reasoning/token budget from settings."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.service import _generate_answer, _generate_sql
from app.config import Settings


class RecordingClient:
    def __init__(self):
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content="SELECT 1")
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_defaults_reason_but_stay_bounded():
    s = _settings()
    assert s.llm_reasoning_effort_sql == "medium"
    assert s.llm_reasoning_effort_text == "low"
    assert 0 < s.llm_max_tokens_explain < s.llm_max_tokens_answer < s.llm_max_tokens_sql


def test_sql_generation_uses_sql_budget():
    client = RecordingClient()
    s = _settings()

    _generate_sql(client, s, "total penjualan semen?")

    call = client.calls[0]
    assert call["reasoning_effort"] == "medium"
    assert call["max_tokens"] == s.llm_max_tokens_sql
    assert call["model"] == s.llm_model_text


def test_answer_uses_light_budget():
    client = RecordingClient()
    s = _settings()

    _generate_answer(client, s, "berapa?", ["total"], [[10]])

    call = client.calls[0]
    assert call["reasoning_effort"] == "low"
    assert call["max_tokens"] == s.llm_max_tokens_answer


def test_empty_effort_omits_reasoning_effort():
    client = RecordingClient()
    s = _settings(llm_reasoning_effort_sql="")

    _generate_sql(client, s, "q")

    assert "reasoning_effort" not in client.calls[0]
    assert client.calls[0]["max_tokens"] == s.llm_max_tokens_sql


# --- retry with the rejected SQL --------------------------------------------------------


def _roles(call: dict) -> list[str]:
    return [m["role"] for m in call["messages"]]


def test_retry_shows_the_model_its_rejected_sql():
    client = RecordingClient()

    _generate_sql(
        client,
        _settings(),
        "hapus semua",
        error_feedback="SQL tidak valid: DELETE tidak diizinkan.",
        previous_sql="DELETE FROM sales_flat",
    )

    call = client.calls[0]
    assert _roles(call) == ["system", "user", "assistant", "user"]
    assert call["messages"][2]["content"] == "DELETE FROM sales_flat"
    assert "tidak valid" in call["messages"][3]["content"]


def test_retry_without_usable_sql_sends_no_empty_assistant_turn():
    client = RecordingClient()

    _generate_sql(
        client, _settings(), "total?", error_feedback="SQL tidak valid: kosong.", previous_sql="  "
    )

    call = client.calls[0]
    assert _roles(call) == ["system", "user"]
    assert call["messages"][1]["content"].startswith("total?")
    assert "SQL tidak valid" in call["messages"][1]["content"]


def test_chat_retries_with_the_first_sql_in_the_conversation(monkeypatch):
    from app import config
    from app.chat import service

    monkeypatch.setattr(
        config, "_settings", _settings(llm_base_url="http://llm.test/v1", llm_api_key="k")
    )
    replies = iter(["DROP TABLE sales_flat", "SELECT SUM(line_total) FROM sales_flat", "Total: 10"])
    calls: list[dict] = []

    class Client:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            calls.append(kwargs)
            message = SimpleNamespace(content=next(replies))
            return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])

    monkeypatch.setattr(service, "make_client", lambda settings: Client())
    monkeypatch.setattr(service, "_execute_sql", lambda db, sql: (["total"], [[10]]))

    result = service.chat(None, "berapa total?")

    assert result["sql"].startswith("SELECT")
    retry = calls[1]["messages"]
    assert [m["role"] for m in retry] == ["system", "user", "assistant", "user"]
    assert retry[2]["content"] == "DROP TABLE sales_flat"


def test_answer_follows_the_requested_language():
    for lang, marker in (("en", "in English"), ("id", "bahasa Indonesia")):
        client = RecordingClient()
        _generate_answer(client, _settings(), "how many?", ["n"], [[1]], lang)
        assert marker in client.calls[0]["messages"][0]["content"]
