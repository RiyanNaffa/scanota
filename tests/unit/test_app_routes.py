"""tests/unit/test_app_routes.py – Every endpoint is mounted, and a broken router stops the app."""

from __future__ import annotations

import sys

import pytest

from app.main import create_app

EXPECTED = {
    ("GET", "/health"),
    ("POST", "/ingest/online"),
    ("POST", "/ingest/online/csv"),
    ("POST", "/ingest/receipt"),
    ("GET", "/transactions"),
    ("GET", "/review"),
    ("GET", "/products"),
    ("GET", "/summary"),
    ("GET", "/restock"),
    ("GET", "/restock/{sku_id}/series"),
    ("POST", "/chat"),
}


def _mounted(app) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if getattr(route, "methods", None)
        for method in route.methods
    }


def test_every_expected_endpoint_is_mounted():
    missing = EXPECTED - _mounted(create_app())
    assert not missing, f"endpoints missing from the app: {sorted(missing)}"


def test_a_router_that_cannot_be_imported_stops_startup(monkeypatch):
    """Regression: main.py used to wrap the router imports in try/except ImportError: pass."""
    monkeypatch.setitem(sys.modules, "app.api.products", None)

    with pytest.raises(ImportError):
        create_app()
