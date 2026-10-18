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
    # Backup vision model, used for a receipt when the main one fails with 5xx or a timeout
    # (after retries). Empty = no fallback. Pick a non-thinking VLM, e.g. DeepSeek-V4.1-Flash.
    llm_model_vision_fallback: str = ""
    llm_model_text: str = "Qwen3.8-27B"
    llm_model_light: str = "MiniCPM5-2B"
    # Per-request timeout for the vision and SQL calls. Tokenfactory models idle on the shared
    # free tier answer a first request in 35-65 s (measured), then in 1-3 s, so 60 was too tight.
    llm_timeout_seconds: int = 120

    # LLM token budget. Qwen3.8-27B thinks at xhigh when no effort is sent, which burns tokens
    # and latency on tasks this small. reasoning_effort keeps some reasoning (SQL needs it) and
    # max_tokens bounds it. Reasoning tokens count toward max_tokens, so a budget that is too
    # small leaves the reply empty (finish_reason "length"; the app logs a warning).
    # Qwen3.8-27B accepts low | medium | xhigh ("high" is a 400). Set an effort to "" to omit
    # the parameter for servers that reject it.
    llm_reasoning_effort_sql: str = "medium"
    llm_reasoning_effort_text: str = "low"
    llm_max_tokens_sql: int = 2048
    llm_max_tokens_answer: int = 1024
    llm_max_tokens_explain: int = 512

    # LLM retry on 429 / 5xx / connection errors. Retry-After is honoured, and Tokenfactory sends
    # 60 s for its per-minute limits, so the cap must stay above 60 or those 429s are never retried.
    llm_max_retries: int = 3
    llm_retry_base_seconds: float = 1.0
    llm_retry_max_seconds: float = 65.0

    # OCR endpoint (POST {LLM_BASE_URL}/ocr, MinerU2.5-Pro on AMD Tokenfactory, billed per page).
    # The text it returns is passed to the vision model as a hint; if OCR is unavailable,
    # extraction continues with the vision model alone. Self-hosted vLLM has no /ocr route: set
    # false. OCR does not stream, so the timeout is generous.
    ocr_enabled: bool = True
    ocr_model: str = "MinerU2.5-Pro"
    ocr_timeout_seconds: int = 60

    # Validation thresholds
    confidence_threshold: float = 0.85
    total_tolerance: int = 0  # Rupiah tolerance for TOTAL_MISMATCH
    match_auto_threshold: float = 90.0
    match_suggest_threshold: float = 70.0

    # Storage
    storage_dir: str = "/srv/storage"
    max_upload_mb: int = 10

    # Safety-stock z for categories without their own entry in app/forecast/category_policy.py.
    # 2.2 is the backtest's value for ~5 % stockouts on goods that keep (1.65 gave ~9 %).
    safety_stock_z: float = 2.2

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
