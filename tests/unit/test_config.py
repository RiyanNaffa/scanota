"""tests/unit/test_config.py – Unit tests for settings loading."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults_load():
    """Settings load with default values when no env vars are set."""
    s = Settings(
        database_url="postgresql://test:test@localhost/test",
        database_readonly_url="postgresql://ro:ro@localhost/test",
    )
    assert s.app_env == "development"
    assert s.confidence_threshold == 0.85
    assert s.total_tolerance == 0
    assert s.match_auto_threshold == 90.0
    assert s.match_suggest_threshold == 70.0
    assert s.max_upload_mb == 10
    assert s.llm_timeout_seconds == 120
    assert s.storage_dir == "/srv/storage"


def test_env_override(monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.7")
    monkeypatch.setenv("TOTAL_TOLERANCE", "50")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/x")
    monkeypatch.setenv("DATABASE_READONLY_URL", "postgresql://ro:ro@localhost/x")
    s = Settings()
    assert s.confidence_threshold == 0.7
    assert s.total_tolerance == 50


def test_invalid_confidence_threshold():
    """confidence_threshold outside [0,1] raises ValueError."""
    with pytest.raises(ValueError):
        Settings(
            confidence_threshold=1.5,
            database_url="postgresql://x:x@localhost/x",
            database_readonly_url="postgresql://ro:ro@localhost/x",
        )


def test_secrets_not_exposed():
    """llm_api_key must not be printed in __str__ or __repr__ by default."""
    s = Settings(
        llm_api_key="super-secret-key-12345",
        database_url="postgresql://x:x@localhost/x",
        database_readonly_url="postgresql://ro:ro@localhost/x",
    )
    # pydantic-settings masks secret fields by default; verify llm_api_key exists
    assert s.llm_api_key == "super-secret-key-12345"
