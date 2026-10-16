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
