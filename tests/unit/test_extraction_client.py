"""tests/unit/test_extraction_client.py – ExtractionClient with a fake SDK client."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app import config
from app.config import Settings
from app.extraction.client import ExtractionClient, ExtractionError

_REQUEST = httpx.Request("POST", "http://llm.test/v1/chat/completions")
_VALID = json.dumps({"date": "2025-01-02", "items": [], "total": 1000})


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    """No real sleeping: zero backoff, two retries."""
    monkeypatch.setattr(
        config,
        "_settings",
        Settings(_env_file=None, llm_retry_base_seconds=0.0, llm_max_retries=2),
    )


class FakeClient:
    """Plays back replies in order; an Exception in the list is raised instead."""

    def __init__(self, replies: list):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        message = SimpleNamespace(content=reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _rate_limit() -> openai.RateLimitError:
    response = httpx.Response(429, headers={"retry-after": "0"}, request=_REQUEST)
    return openai.RateLimitError("slow down", response=response, body=None)


def _server_error() -> openai.InternalServerError:
    response = httpx.Response(503, request=_REQUEST)
    return openai.InternalServerError("no workers", response=response, body=None)


def _timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=_REQUEST)


def _models(fake: FakeClient) -> list[str]:
    return [c["model"] for c in fake.calls]


def _user_text(call: dict) -> str:
    return call["messages"][1]["content"][1]["text"]


def test_extract_without_ocr_uses_plain_prompt():
    fake = FakeClient([_VALID])

    result = ExtractionClient(openai_client=fake, model="m").extract(b"img")

    assert result.total == 1000
    assert "<ocr>" not in _user_text(fake.calls[0])


def test_extract_with_ocr_adds_hint_to_prompt():
    fake = FakeClient([_VALID])

    ExtractionClient(openai_client=fake, model="m").extract(b"img", ocr_text="Semen 3R 50.000")

    text = _user_text(fake.calls[0])
    assert "<ocr>\nSemen 3R 50.000\n</ocr>" in text
    assert "trust the image" in text


def test_bad_json_gets_one_feedback_retry():
    fake = FakeClient(["not json", _VALID])

    result = ExtractionClient(openai_client=fake, model="m").extract(b"img")

    assert result.total == 1000
    assert len(fake.calls) == 2
    roles = [m["role"] for m in fake.calls[1]["messages"]]
    assert roles[-2:] == ["assistant", "user"]
    assert fake.calls[1]["messages"][-2]["content"] == "not json"


def test_bad_json_twice_raises_extraction_error():
    fake = FakeClient(["nope", "still nope"])

    with pytest.raises(ExtractionError, match="after retry"):
        ExtractionClient(openai_client=fake, model="m").extract(b"img")


def test_rate_limit_is_retried_inside_one_attempt():
    fake = FakeClient([_rate_limit(), _VALID])

    result = ExtractionClient(openai_client=fake, model="m").extract(b"img")

    assert result.total == 1000
    assert len(fake.calls) == 2
    # Same messages both times: the 429 retry is not a feedback retry.
    assert fake.calls[0]["messages"] == fake.calls[1]["messages"]


def test_rate_limit_exhausted_raises_without_feedback_retry():
    fake = FakeClient([_rate_limit() for _ in range(10)])

    with pytest.raises(ExtractionError, match="request failed"):
        ExtractionClient(openai_client=fake, model="m").extract(b"img")

    assert len(fake.calls) == 3  # first try + llm_max_retries (2), nothing more


# --- fallback model ------------------------------------------------------------------


def test_falls_back_when_primary_stays_down_with_5xx():
    # llm_max_retries=2 -> 3 failed tries on the primary, then the fallback answers.
    fake = FakeClient([_server_error(), _server_error(), _server_error(), _VALID])

    result = ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(
        b"img"
    )

    assert result.total == 1000
    assert _models(fake) == ["main", "main", "main", "backup"]


def test_falls_back_immediately_on_timeout():
    """Timeouts are not retried, so the fallback takes over after the first one."""
    fake = FakeClient([_timeout(), _VALID])

    ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(b"img")

    assert _models(fake) == ["main", "backup"]


def test_fallback_is_sticky_for_the_feedback_retry():
    fake = FakeClient([_timeout(), "not json", _VALID])

    ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(b"img")

    assert _models(fake) == ["main", "backup", "backup"]


def test_no_fallback_when_primary_works():
    fake = FakeClient([_VALID])

    ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(b"img")

    assert _models(fake) == ["main"]


def test_rate_limit_does_not_trigger_fallback():
    fake = FakeClient([_rate_limit() for _ in range(10)])

    with pytest.raises(ExtractionError):
        ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(b"img")

    assert set(_models(fake)) == {"main"}


@pytest.mark.parametrize("fallback", ["", "main"])
def test_disabled_or_same_as_primary_means_no_fallback(fallback):
    fake = FakeClient([_server_error() for _ in range(10)])

    with pytest.raises(ExtractionError, match="request failed"):
        ExtractionClient(openai_client=fake, model="main", fallback_model=fallback).extract(b"img")

    assert set(_models(fake)) == {"main"}


def test_error_when_fallback_is_down_too():
    fake = FakeClient([_server_error() for _ in range(10)])

    with pytest.raises(ExtractionError, match="request failed"):
        ExtractionClient(openai_client=fake, model="main", fallback_model="backup").extract(b"img")

    assert _models(fake) == ["main"] * 3 + ["backup"] * 3


def test_fallback_defaults_to_setting(monkeypatch):
    monkeypatch.setattr(
        config,
        "_settings",
        Settings(
            _env_file=None,
            llm_retry_base_seconds=0.0,
            llm_max_retries=0,
            llm_model_vision_fallback="from-settings",
        ),
    )
    fake = FakeClient([_server_error(), _VALID])

    ExtractionClient(openai_client=fake, model="main").extract(b"img")

    assert _models(fake) == ["main", "from-settings"]


def test_request_timeout_comes_from_settings(monkeypatch):
    """Tokenfactory's first request to an idle model takes 35-65 s; 60 s was too tight."""
    monkeypatch.setattr(
        config,
        "_settings",
        Settings(_env_file=None, llm_retry_base_seconds=0.0, llm_timeout_seconds=90),
    )
    fake = FakeClient([_VALID])

    ExtractionClient(openai_client=fake, model="m").extract(b"img")

    assert fake.calls[0]["timeout"] == 90


def test_explicit_timeout_wins_over_settings():
    fake = FakeClient([_VALID])

    ExtractionClient(openai_client=fake, model="m", timeout=15).extract(b"img")

    assert fake.calls[0]["timeout"] == 15
