"""app/llm.py – Shared helpers for OpenAI-compatible LLM calls: client, token budget, retry."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import openai
from openai import OpenAI

logger = logging.getLogger(__name__)

T = TypeVar("T")


def make_client(settings) -> OpenAI:
    """Build the SDK client. SDK-level retries are off: call_with_retry owns the retry policy,
    otherwise a 429 would be retried by both and the waits would multiply."""
    return OpenAI(
        base_url=settings.llm_base_url or None,
        api_key=settings.llm_api_key or "no-key",
        max_retries=0,
    )


def completion_kwargs(effort: str, max_tokens: int) -> dict[str, Any]:
    """Token budget for one chat completion; an empty effort omits reasoning_effort."""
    kwargs: dict[str, Any] = {"max_tokens": max_tokens}
    if effort:
        kwargs["reasoning_effort"] = effort
    return kwargs


def parse_retry_after(headers: Mapping[str, str] | None) -> float | None:
    """Seconds from a Retry-After (or retry-after-ms) header; None if absent or unparseable."""
    if not headers:
        return None
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return max(float(ms) / 1000.0, 0.0)
        except ValueError:
            pass
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:  # HTTP-date form
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - datetime.now(UTC)).total_seconds(), 0.0)


def retry_delay(
    attempt: int,
    retry_after: float | None,
    *,
    max_retries: int,
    base_delay: float,
    max_delay: float,
) -> float | None:
    """Seconds to sleep before retry number attempt+1, or None when retrying is pointless.

    A server-provided Retry-After wins over backoff; if it exceeds max_delay we give up now
    instead of sleeping a shorter time and being rejected again.
    """
    if attempt >= max_retries:
        return None
    if retry_after is not None:
        return retry_after if retry_after <= max_delay else None
    return min(max_delay, base_delay * 2**attempt) * random.uniform(0.5, 1.0)


def message_text(resp, what: str) -> str:
    """Stripped content of the first choice; warns when max_tokens cut the reply short.

    Reasoning tokens count toward max_tokens, so an exhausted budget shows up as empty content
    with finish_reason "length" rather than as an error.
    """
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        logger.warning(
            "LLM reply for %s hit max_tokens (reasoning counts toward it); "
            "raise LLM_MAX_TOKENS_* or lower the reasoning effort",
            what,
        )
    return (choice.message.content or "").strip()


def call_with_retry(
    fn: Callable[[], T],
    *,
    settings=None,
    sleep: Callable[[float], None] = time.sleep,
    max_retries: int | None = None,
    max_delay: float | None = None,
) -> T:
    """Run fn(), retrying 429, 5xx and connection errors with Retry-After / exponential backoff.

    Timeouts are not retried: the request already used its whole time budget. max_retries and
    max_delay override the settings for optional calls that should not stall the caller.
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    retries = settings.llm_max_retries if max_retries is None else max_retries
    cap = settings.llm_retry_max_seconds if max_delay is None else max_delay

    attempt = 0
    while True:
        try:
            return fn()
        except openai.APITimeoutError:
            raise
        except (
            openai.RateLimitError,
            openai.InternalServerError,
            openai.APIConnectionError,
        ) as exc:
            response = getattr(exc, "response", None)
            delay = retry_delay(
                attempt,
                parse_retry_after(response.headers) if response is not None else None,
                max_retries=retries,
                base_delay=settings.llm_retry_base_seconds,
                max_delay=cap,
            )
            if delay is None:
                raise
            attempt += 1
            logger.warning(
                "LLM call failed (%s); retry %d/%d in %.1fs",
                type(exc).__name__,
                attempt,
                retries,
                delay,
            )
            sleep(delay)
