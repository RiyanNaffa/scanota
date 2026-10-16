"""app/extraction/ocr.py – OCR client for the MinerU2.5-Pro endpoint (POST {LLM_BASE_URL}/ocr).

The OCR text is a hint for the vision model, not a replacement: the image stays the source of
truth. Every failure returns None so extraction continues with the vision model alone.

Contract (AMD Token Factory docs): request {"model", "document": {"type": "document_url",
"document_url": <url>}, "pages"}; response pages[].markdown plus usage_info.pages_processed.
The docs only show an https URL, and a receipt upload has none, so the image is sent as a
base64 data URL. That part is UNVERIFIED: if the gateway rejects data URLs, the 4xx is logged
(with the response body) and extraction falls back to the vision model alone.
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.llm import parse_retry_after, retry_delay

logger = logging.getLogger(__name__)

MAX_OCR_CHARS = 6000  # bound the prompt size; a receipt is far shorter than this
_UNSUPPORTED_STATUS = {404, 405, 501}
_TEXT_KEYS = ("markdown", "text", "content")
_CONTAINER_KEYS = ("pages", "results", "result", "data", "output")

# URLs that answered "no such route" (e.g. self-hosted vLLM): skip them for the process lifetime
# instead of paying a failed round trip on every receipt.
_unsupported_urls: set[str] = set()


class OcrClient:
    def __init__(
        self,
        http_client: httpx.Client | None = None,
        settings=None,
        sleep=time.sleep,
    ) -> None:
        if settings is None:
            from app.config import get_settings

            settings = get_settings()
        self._settings = settings
        self._http = http_client
        self._sleep = sleep
        base = settings.llm_base_url.rstrip("/")
        self._url = f"{base}/ocr"
        self._enabled = bool(settings.ocr_enabled and base and settings.llm_api_key)

    def read(self, image_bytes: bytes) -> str | None:
        """Return the OCR text of a receipt image, or None when OCR is off or unavailable."""
        if not self._enabled or self._url in _unsupported_urls:
            return None
        try:
            return self._post_with_retry(image_bytes)
        except Exception as exc:  # OCR is an accuracy aid; never fail the receipt over it
            logger.warning("OCR unavailable, continuing with vision model only: %s", exc)
            return None

    def _post_with_retry(self, image_bytes: bytes) -> str | None:
        s = self._settings
        headers = {"Authorization": f"Bearer {s.llm_api_key}"}
        payload = self._build_payload(image_bytes)
        attempt = 0
        while True:
            resp = self._post(headers, payload)
            if resp.status_code in _UNSUPPORTED_STATUS:
                _unsupported_urls.add(self._url)
                logger.warning(
                    "OCR endpoint %s returned %s; disabled until restart. "
                    "Set OCR_ENABLED=false if this deployment has no /ocr route.",
                    self._url, resp.status_code,
                )
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                delay = retry_delay(
                    attempt,
                    parse_retry_after(resp.headers),
                    max_retries=s.llm_max_retries,
                    base_delay=s.llm_retry_base_seconds,
                    max_delay=s.llm_retry_max_seconds,
                )
                if delay is not None:
                    attempt += 1
                    logger.warning(
                        "OCR returned %s; retry %d/%d in %.1fs",
                        resp.status_code, attempt, s.llm_max_retries, delay,
                    )
                    self._sleep(delay)
                    continue
            if resp.status_code >= 400:
                # Keep the body: it says why (bad document, quota, auth) and the SDK-style
                # raise_for_status message would drop it.
                raise RuntimeError(f"OCR HTTP {resp.status_code}: {resp.text[:300]}")
            text = self._extract_text(resp.json())[:MAX_OCR_CHARS]
            logger.info("OCR read %d characters", len(text))
            return text or None

    def _post(self, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        timeout = self._settings.ocr_timeout_seconds
        if self._http is not None:
            return self._http.post(self._url, headers=headers, json=payload, timeout=timeout)
        with httpx.Client() as client:
            return client.post(self._url, headers=headers, json=payload, timeout=timeout)

    def _build_payload(self, image_bytes: bytes) -> dict[str, Any]:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return {
            "model": self._settings.ocr_model,
            "document": {
                "type": "document_url",
                "document_url": f"data:image/jpeg;base64,{b64}",
            },
        }

    @classmethod
    def _extract_text(cls, node: Any) -> str:
        """Pull the text out of an OCR response, tolerating the common shapes."""
        if isinstance(node, str):
            return node.strip()
        if isinstance(node, list):
            return "\n".join(t for t in (cls._extract_text(n) for n in node) if t)
        if isinstance(node, dict):
            for key in _TEXT_KEYS + _CONTAINER_KEYS:
                if key in node:
                    text = cls._extract_text(node[key])
                    if text:
                        return text
        return ""
