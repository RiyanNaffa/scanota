"""app/evolus/client.py – Evolus API client."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

_ENDPOINTS_PATH = "evolus/endpoints.yaml"
_call_counts: dict[str, int] = defaultdict(int)


class EvolusNotConfigured(Exception):
    pass


def _load_endpoints() -> dict:
    try:
        with open(_ENDPOINTS_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


class EvolusClient:
    def __init__(self) -> None:
        from app.config import get_settings

        s = get_settings()
        self._base_url = s.evolus_base_url.rstrip("/") if s.evolus_base_url else ""
        self._api_key = s.evolus_api_key
        self._workspace_id = s.evolus_workspace_id
        self._endpoints = _load_endpoints()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _get_endpoint(self, operation: str) -> dict:
        ep = self._endpoints.get(operation, {})
        if not ep or ep.get("path") == "TO_CONFIRM" or ep.get("request_format") == "TO_CONFIRM":
            raise EvolusNotConfigured(
                f"Evolus operation '{operation}' is not configured. "
                f"Edit evolus/endpoints.yaml and fill in the actual paths."
            )
        return ep

    def call(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Call an Evolus operation. Retries once on 5xx or timeout."""
        ep = self._get_endpoint(operation)
        url = f"{self._base_url}{ep['path']}"
        method = ep.get("method", "POST").upper()

        _call_counts[operation] += 1
        start = time.monotonic()

        for attempt in range(2):
            try:
                with httpx.Client(timeout=30) as client:
                    if method == "GET":
                        resp = client.get(url, headers=self._headers(), params=payload)
                    else:
                        resp = client.post(url, headers=self._headers(), json=payload)

                duration = time.monotonic() - start
                logger.info(
                    "evolus op=%s status=%s duration=%.2fs",
                    operation, resp.status_code, duration,
                )
                if resp.status_code >= 500 and attempt == 0:
                    time.sleep(1)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.TimeoutException:
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise
        return {}

    def get_stats(self) -> dict[str, int]:
        return dict(_call_counts)
