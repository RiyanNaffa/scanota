"""tests/unit/test_ocr.py – OCR hint client (httpx mocked, no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.extraction import ocr
from app.extraction.ocr import MAX_OCR_CHARS, OcrClient

BASE = "http://llm.test/v1"


@pytest.fixture(autouse=True)
def _clear_unsupported():
    ocr._unsupported_urls.clear()
    yield
    ocr._unsupported_urls.clear()


def _settings(**overrides) -> Settings:
    values = {"llm_base_url": BASE, "llm_api_key": "k", "llm_retry_base_seconds": 0.0}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _client(handler, **settings_overrides) -> tuple[OcrClient, list[float]]:
    sleeps: list[float] = []
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OcrClient(http, _settings(**settings_overrides), sleep=sleeps.append), sleeps


def test_reads_text_and_sends_expected_request():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"pages": [{"markdown": "Semen 3R  50.000"}]})

    client, _ = _client(handler)

    assert client.read(b"jpegbytes") == "Semen 3R  50.000"
    assert str(seen[0].url) == f"{BASE}/ocr"
    assert seen[0].headers["authorization"] == "Bearer k"
    body = json.loads(seen[0].content)
    assert body["model"] == "MinerU2.5-Pro"
    assert body["document"]["type"] == "document_url"
    assert body["document"]["document_url"].startswith("data:image/jpeg;base64,")


def test_reads_documented_response_shape():
    payload = {
        "pages": [{"index": 0, "markdown": "Nota\nSemen 3R"}],
        "usage_info": {"pages_processed": 1},
    }
    client, _ = _client(lambda r: httpx.Response(200, json=payload))
    assert client.read(b"x") == "Nota\nSemen 3R"


@pytest.mark.parametrize(
    "payload",
    [
        {"pages": [{"markdown": "a"}, {"markdown": "b"}]},
        {"text": "a\nb"},
        {"data": {"content": "a\nb"}},
        {"choices": []},  # no text anywhere
    ],
)
def test_extract_text_shapes(payload):
    text = OcrClient._extract_text(payload)
    if "choices" in payload:
        assert text == ""
    else:
        assert text.replace("\n", "") == "ab"


def test_disabled_makes_no_request():
    client, _ = _client(lambda r: pytest.fail("must not call"), ocr_enabled=False)
    assert client.read(b"x") is None


def test_missing_api_key_makes_no_request():
    client, _ = _client(lambda r: pytest.fail("must not call"), llm_api_key="")
    assert client.read(b"x") is None


def test_retries_429_with_retry_after():
    responses = [
        httpx.Response(429, headers={"retry-after": "3"}),
        httpx.Response(200, json={"text": "ok"}),
    ]
    client, sleeps = _client(lambda r: responses.pop(0))

    assert client.read(b"x") == "ok"
    assert sleeps == [3.0]


def test_gives_up_after_max_retries_and_returns_none():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, headers={"retry-after": "0"})

    client, sleeps = _client(handler, llm_max_retries=2)

    assert client.read(b"x") is None
    assert calls["n"] == 3 and len(sleeps) == 2


def test_missing_route_disables_ocr_for_later_calls():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    client, _ = _client(handler)

    assert client.read(b"x") is None
    assert client.read(b"x") is None
    assert calls["n"] == 1


def test_client_error_returns_none_without_retry_and_logs_body(caplog):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(422, json={"detail": "bad document"})

    client, sleeps = _client(handler)

    with caplog.at_level("WARNING"):
        assert client.read(b"x") is None
    assert calls["n"] == 1 and sleeps == []
    assert "422" in caplog.text and "bad document" in caplog.text


def test_network_error_returns_none():
    def handler(request):
        raise httpx.ConnectError("refused")

    client, _ = _client(handler)
    assert client.read(b"x") is None


def test_text_is_truncated():
    client, _ = _client(lambda r: httpx.Response(200, json={"text": "a" * (MAX_OCR_CHARS + 500)}))
    assert len(client.read(b"x")) == MAX_OCR_CHARS


def test_empty_text_returns_none():
    client, _ = _client(lambda r: httpx.Response(200, json={"pages": [{"markdown": "  "}]}))
    assert client.read(b"x") is None
