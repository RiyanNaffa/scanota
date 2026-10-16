"""tests/integration/test_health.py – Integration test for the health endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.integration
def test_health_ok():
    """GET /health returns 200 with status=ok."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # db may be "ok" or "error" depending on environment; both are valid responses
    assert data["db"] in ("ok", "error")
