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
