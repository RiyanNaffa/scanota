"""app/extraction/client.py – LLM client for receipt extraction.

Uses the official openai SDK with a configurable base_url (OpenAI-compatible).
Retries once on parse/validation failure with the error message appended.
"""
from __future__ import annotations

import base64
import json
import logging
import re

from openai import OpenAI

from app.extraction.prompts import RETRY_PROMPT_TEMPLATE, SYSTEM_PROMPT, USER_PROMPT
from app.extraction.schema import ExtractionResult

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
        timeout: int = 60,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self._client = openai_client or OpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key or "no-key",
        )
        self._model = model or settings.llm_model_vision
        self._timeout = timeout

    def extract(self, image_bytes: bytes) -> ExtractionResult:
        """Extract structured data from receipt image bytes.

        Args:
            image_bytes: JPEG image bytes (preprocessed).

        Returns:
            ExtractionResult validated by Pydantic.

        Raises:
            ExtractionError: if both attempts fail.
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{b64}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {"type": "text", "text": USER_PROMPT},
                ],
            },
        ]

        # First attempt
        try:
            raw_text = self._call_llm(messages)
            return self._parse_response(raw_text)
        except (json.JSONDecodeError, ValueError, Exception) as exc:
            error_msg = str(exc)
            logger.warning("Extraction attempt 1 failed: %s", error_msg)

        # Retry with error feedback
        messages.append({"role": "assistant", "content": raw_text if "raw_text" in dir() else ""})
        messages.append(
            {"role": "user", "content": RETRY_PROMPT_TEMPLATE.format(error=error_msg)}
        )
        try:
            raw_text2 = self._call_llm(messages)
            return self._parse_response(raw_text2)
        except Exception as exc2:
            raise ExtractionError(
                f"Receipt extraction failed after retry: {exc2}"
            ) from exc2

    def _call_llm(self, messages: list) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0,
            timeout=self._timeout,
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
