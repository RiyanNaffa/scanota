"""app/config.py – Application settings via pydantic-settings."""
from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"

    # Database
    database_url: str = "postgresql://scanota:change-me@db:5432/scanota"
    database_readonly_url: str = "postgresql://scanota_ro:change-me@db:5432/scanota"

    # LLM
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_vision: str = "MiniCPM-V-4.7-35B-A3B"
    llm_model_text: str = "Qwen3.8-27B"
    llm_model_light: str = "MiniCPM5-2B"
    llm_timeout_seconds: int = 60

    # Validation thresholds
    confidence_threshold: float = 0.85
    total_tolerance: int = 0  # Rupiah tolerance for TOTAL_MISMATCH
    match_auto_threshold: float = 90.0
    match_suggest_threshold: float = 70.0

    # Storage
    storage_dir: str = "/srv/storage"
    max_upload_mb: int = 10

    # Evolus
    evolus_base_url: str = ""
    evolus_api_key: str = ""
    evolus_workspace_id: str = ""
    evolus_enabled: bool = False
    extraction_backend: str = "direct"  # "direct" or "evolus"

    # Safety stock z-score (default ~95% service level)
    safety_stock_z: float = 1.65

    @field_validator("confidence_threshold")
    @classmethod
    def check_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1")
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
