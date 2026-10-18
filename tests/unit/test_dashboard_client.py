"""tests/unit/test_dashboard_client.py – Dashboard shows the API's own error message."""

from __future__ import annotations

import httpx

from dashboard.api_client import _error

_REQUEST = httpx.Request("POST", "http://api/ingest/receipt")


def _status_error(status: int, **kwargs) -> httpx.HTTPStatusError:
    response = httpx.Response(status, request=_REQUEST, **kwargs)
    return httpx.HTTPStatusError("boom", request=_REQUEST, response=response)


def test_uses_api_detail_message():
    err = _status_error(502, json={"detail": "Model sedang sibuk."})
    assert _error(err) == {"error": "Model sedang sibuk."}


def test_falls_back_to_exception_text_without_string_detail():
    err = _status_error(422, json={"detail": [{"msg": "field required"}]})
    assert _error(err) == {"error": "boom"}


def test_falls_back_when_body_is_not_json():
    err = _status_error(500, text="<html>oops</html>")
    assert _error(err) == {"error": "boom"}


def test_timeout_with_empty_message_still_says_something():
    assert _error(httpx.ReadTimeout("", request=_REQUEST)) == {"error": "ReadTimeout"}


def _real_api():
    """The real api_client. The view tests replace its functions with canned ones, and Streamlit's
    AppTest can leave that patched module in sys.modules, so reload it before testing the original."""
    import importlib

    import dashboard.api_client as api

    return importlib.reload(api)


def test_health_timeout_means_busy_not_offline(monkeypatch):
    api = _real_api()

    def slow(*args, **kwargs):
        raise httpx.ReadTimeout("", request=_REQUEST)

    monkeypatch.setattr(api.httpx, "get", slow)

    health = api.health()
    assert health["status"] == "ok" and health["busy"] is True


def test_health_refused_connection_is_offline(monkeypatch):
    api = _real_api()

    def refused(*args, **kwargs):
        raise httpx.ConnectError("refused", request=_REQUEST)

    monkeypatch.setattr(api.httpx, "get", refused)

    assert "error" in api.health()


def test_the_forecast_calls_wait_longer_than_an_ordinary_call(monkeypatch):
    """/restock computes the forecast per request; on a small VM that outlasts the 30 s default."""
    api = _real_api()
    waits: dict[str, float] = {}

    def fake_get(url, params=None, timeout=None):
        waits[url] = timeout
        return httpx.Response(200, json=[], request=_REQUEST)

    monkeypatch.setattr(api.httpx, "get", fake_get)
    api.restock(lang="id")
    api.forecast_series("ISO001")
    api.transactions(limit=1)

    restock_wait, series_wait, other_wait = list(waits.values())
    assert restock_wait == series_wait == 120
    assert other_wait == 30


def test_chat_can_skip_the_written_answer_and_fetch_it_separately(monkeypatch):
    api = _real_api()
    sent: dict[str, dict] = {}

    def fake_post(url, json=None, files=None, data=None, timeout=None):
        sent[url.rsplit("/chat", 1)[-1] or "/"] = {"json": json, "timeout": timeout}
        return httpx.Response(200, json={"answer": None}, request=_REQUEST)

    monkeypatch.setattr(api.httpx, "post", fake_post)
    api.chat("q", "en", answer=False)
    api.chat_answer("q", ["n"], [[1]], "en")

    assert sent["/"]["json"] == {"question": "q", "lang": "en", "answer": False}
    assert sent["/answer"]["json"] == {
        "question": "q",
        "columns": ["n"],
        "rows": [[1]],
        "lang": "en",
    }
    assert sent["/answer"]["timeout"] == 90  # not the 300 s of the query call
