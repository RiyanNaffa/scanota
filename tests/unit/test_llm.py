"""tests/unit/test_llm.py – Retry policy and token-budget helpers."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.config import Settings
from app.llm import (
    call_with_retry,
    completion_kwargs,
    message_text,
    parse_retry_after,
    retry_delay,
)

_REQUEST = httpx.Request("POST", "http://llm.test/v1/chat/completions")


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _status_error(cls, status: int, headers: dict[str, str] | None = None):
    response = httpx.Response(status, headers=headers or {}, request=_REQUEST)
    return cls("boom", response=response, body=None)


def _flaky(errors: list[Exception], result="ok"):
    """Callable that raises each error in turn, then returns result."""
    calls = {"n": 0}

    def fn():
        i = calls["n"]
        calls["n"] += 1
        if i < len(errors):
            raise errors[i]
        return result

    return fn, calls


# --- parse_retry_after ---------------------------------------------------------------


def test_parse_retry_after_seconds():
    assert parse_retry_after({"retry-after": "7"}) == 7.0


def test_parse_retry_after_milliseconds_wins():
    assert parse_retry_after({"retry-after-ms": "1500", "retry-after": "9"}) == 1.5


def test_parse_retry_after_http_date():
    when = datetime.now(UTC) + timedelta(seconds=30)
    delay = parse_retry_after({"retry-after": format_datetime(when, usegmt=True)})
    assert delay is not None and 25 <= delay <= 31


def test_parse_retry_after_missing_or_garbage():
    assert parse_retry_after(None) is None
    assert parse_retry_after({}) is None
    assert parse_retry_after({"retry-after": "soon"}) is None


# --- retry_delay ---------------------------------------------------------------------


def test_retry_delay_gives_up_after_max_retries():
    assert retry_delay(3, None, max_retries=3, base_delay=1, max_delay=30) is None


def test_retry_delay_honours_retry_after():
    assert retry_delay(0, 5.0, max_retries=3, base_delay=1, max_delay=30) == 5.0


def test_retry_delay_gives_up_when_retry_after_exceeds_cap():
    assert retry_delay(0, 120.0, max_retries=3, base_delay=1, max_delay=30) is None


def test_retry_delay_backoff_grows_and_is_capped():
    for attempt, ceiling in [(0, 1), (1, 2), (2, 4), (10, 30)]:
        delay = retry_delay(attempt, None, max_retries=99, base_delay=1, max_delay=30)
        assert ceiling / 2 <= delay <= ceiling


# --- call_with_retry -----------------------------------------------------------------


def test_retries_429_honouring_retry_after_then_succeeds():
    errors = [
        _status_error(openai.RateLimitError, 429, {"retry-after": "2"}),
        _status_error(openai.RateLimitError, 429, {"retry-after": "4"}),
    ]
    fn, calls = _flaky(errors)
    sleeps: list[float] = []

    assert call_with_retry(fn, settings=_settings(), sleep=sleeps.append) == "ok"
    assert sleeps == [2.0, 4.0]
    assert calls["n"] == 3


def test_429_without_retry_after_uses_backoff():
    fn, _ = _flaky([_status_error(openai.RateLimitError, 429)])
    sleeps: list[float] = []

    call_with_retry(fn, settings=_settings(), sleep=sleeps.append)
    assert len(sleeps) == 1 and 0.5 <= sleeps[0] <= 1.0


def test_raises_after_exhausting_retries():
    errors = [_status_error(openai.RateLimitError, 429) for _ in range(10)]
    fn, calls = _flaky(errors)

    with pytest.raises(openai.RateLimitError):
        call_with_retry(fn, settings=_settings(llm_max_retries=2), sleep=lambda _: None)
    assert calls["n"] == 3  # first try + 2 retries


def test_gives_up_immediately_when_retry_after_exceeds_cap():
    fn, calls = _flaky([_status_error(openai.RateLimitError, 429, {"retry-after": "300"})])

    with pytest.raises(openai.RateLimitError):
        call_with_retry(fn, settings=_settings(), sleep=lambda _: pytest.fail("must not sleep"))
    assert calls["n"] == 1


def test_retries_5xx_and_connection_errors():
    fn, calls = _flaky(
        [
            _status_error(openai.InternalServerError, 503),
            openai.APIConnectionError(request=_REQUEST),
        ]
    )
    assert call_with_retry(fn, settings=_settings(), sleep=lambda _: None) == "ok"
    assert calls["n"] == 3


def test_timeouts_are_not_retried():
    fn, calls = _flaky([openai.APITimeoutError(request=_REQUEST)])

    with pytest.raises(openai.APITimeoutError):
        call_with_retry(fn, settings=_settings(), sleep=lambda _: pytest.fail("must not sleep"))
    assert calls["n"] == 1


def test_client_errors_are_not_retried():
    fn, calls = _flaky([_status_error(openai.BadRequestError, 400)])

    with pytest.raises(openai.BadRequestError):
        call_with_retry(fn, settings=_settings(), sleep=lambda _: pytest.fail("must not sleep"))
    assert calls["n"] == 1


def test_default_cap_honours_tokenfactory_60s_retry_after():
    """Tokenfactory's per-minute 429s send Retry-After: 60; the default cap must not reject it."""
    fn, calls = _flaky([_status_error(openai.RateLimitError, 429, {"retry-after": "60"})])
    sleeps: list[float] = []

    assert call_with_retry(fn, settings=_settings(), sleep=sleeps.append) == "ok"
    assert sleeps == [60.0] and calls["n"] == 2


def test_overrides_make_optional_calls_give_up_on_long_waits():
    fn, calls = _flaky([_status_error(openai.RateLimitError, 429, {"retry-after": "60"})])

    with pytest.raises(openai.RateLimitError):
        call_with_retry(
            fn,
            settings=_settings(),
            sleep=lambda _: pytest.fail("must not sleep"),
            max_retries=1,
            max_delay=5.0,
        )
    assert calls["n"] == 1


def test_overrides_still_retry_short_waits():
    fn, calls = _flaky([_status_error(openai.RateLimitError, 429, {"retry-after": "1"})])
    sleeps: list[float] = []

    call_with_retry(fn, settings=_settings(), sleep=sleeps.append, max_retries=1, max_delay=5.0)
    assert sleeps == [1.0] and calls["n"] == 2


# --- message_text --------------------------------------------------------------------


def _resp(content, finish_reason="stop"):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def test_message_text_strips():
    assert message_text(_resp("  SELECT 1 \n"), "sql") == "SELECT 1"


def test_message_text_none_content_is_empty():
    assert message_text(_resp(None), "sql") == ""


def test_message_text_warns_when_budget_cut_the_reply(caplog):
    with caplog.at_level("WARNING"):
        assert message_text(_resp("", finish_reason="length"), "SQL generation") == ""
    assert "SQL generation" in caplog.text and "max_tokens" in caplog.text


def test_message_text_is_quiet_on_normal_stop(caplog):
    with caplog.at_level("WARNING"):
        message_text(_resp("ok"), "sql")
    assert caplog.text == ""


# --- completion_kwargs ---------------------------------------------------------------


def test_completion_kwargs_with_effort():
    assert completion_kwargs("low", 384) == {"max_tokens": 384, "reasoning_effort": "low"}


def test_completion_kwargs_empty_effort_is_omitted():
    assert completion_kwargs("", 384) == {"max_tokens": 384}
