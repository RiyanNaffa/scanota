"""app/extraction/client.py – LLM client for receipt extraction.

Uses the official openai SDK with a configurable base_url (OpenAI-compatible).
Transient API errors (429, 5xx) are retried with backoff in app.llm; if the vision model is
still down (5xx or timeout) the optional LLM_MODEL_VISION_FALLBACK model takes over. On a
parse/validation failure the model gets one more try with the error message appended.
"""

from __future__ import annotations

import base64
import json
import logging
import re

import openai
from openai import OpenAI

from app.extraction.prompts import (
    RETRY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    USER_PROMPT,
    USER_PROMPT_WITH_OCR,
)
from app.extraction.schema import ExtractionResult
from app.llm import call_with_retry, make_client

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    pass


class ExtractionClient:
    """Extracts structured data from a receipt image using an LLM.

    Accepts an injected SDK client so tests can fake it.
    """

    def __init__(
        self,
        openai_client: OpenAI | None = None,
        model: str | None = None,
        timeout: int | None = None,
        fallback_model: str | None = None,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self._client = openai_client or make_client(settings)
        self._model = model or settings.llm_model_vision
        # None reads the setting; "" disables the fallback.
        fallback = settings.llm_model_vision_fallback if fallback_model is None else fallback_model
        self._fallback = fallback if fallback and fallback != self._model else ""
        self._on_fallback = False  # sticky for this client, so a feedback retry stays put
        self._timeout = timeout or settings.llm_timeout_seconds

    def extract(self, image_bytes: bytes, ocr_text: str | None = None) -> ExtractionResult:
        """Extract structured data from receipt image bytes.

        Args:
            image_bytes: JPEG image bytes (preprocessed).
            ocr_text: Optional OCR text of the same image, given to the model as a hint.

        Returns:
            ExtractionResult validated by Pydantic.

        Raises:
            ExtractionError: if the API call fails or both parse attempts fail.
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{b64}"
        user_prompt = USER_PROMPT_WITH_OCR.format(ocr_text=ocr_text) if ocr_text else USER_PROMPT

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {"type": "text", "text": user_prompt},
                ],
            },
        ]

        # First attempt
        raw_text = ""
        try:
            raw_text = self._call_llm(messages)
            return self._parse_response(raw_text)
        except openai.OpenAIError as exc:
            # Retries are already spent in call_with_retry; asking again would not help.
            raise ExtractionError(f"Receipt extraction request failed: {exc}") from exc
        except Exception as exc:
            error_msg = str(exc)
            logger.warning("Extraction attempt 1 failed: %s", error_msg)

        # Retry with error feedback
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({"role": "user", "content": RETRY_PROMPT_TEMPLATE.format(error=error_msg)})
        try:
            raw_text2 = self._call_llm(messages)
            return self._parse_response(raw_text2)
        except Exception as exc2:
            raise ExtractionError(f"Receipt extraction failed after retry: {exc2}") from exc2

    def _call_llm(self, messages: list) -> str:
        """Call the vision model, switching to the fallback if it is down (5xx or timeout).

        429 and connection errors do not switch: the rate limit is per key, and an unreachable
        gateway is unreachable for every model.
        """
        if self._on_fallback:
            return self._complete(self._fallback, messages)
        try:
            return self._complete(self._model, messages)
        except (openai.InternalServerError, openai.APITimeoutError) as exc:
            if not self._fallback:
                raise
            logger.warning(
                "Vision model %s unavailable (%s); falling back to %s",
                self._model,
                type(exc).__name__,
                self._fallback,
            )
            self._on_fallback = True
            return self._complete(self._fallback, messages)

    def _complete(self, model: str, messages: list) -> str:
        response = call_with_retry(
            lambda: self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                timeout=self._timeout,
            )
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_response(raw: str) -> ExtractionResult:
        """Strip markdown fences, parse JSON, validate with Pydantic."""
        text = raw.strip()
        # Remove ```json ... ``` fences
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
        data = json.loads(text)
        return ExtractionResult.model_validate(data)
