"""Configuration. Environment-driven, validated once at boot."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JARVIS_", env_file=".env", extra="ignore", case_sensitive=False
    )

    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # Providers. Absent keys simply mean that adapter is not registered —
    # Jarvis always boots, degrading to whatever is available (at minimum echo).
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    local_llm_base_url: str = "http://localhost:11434/v1"
    enable_local_llm: bool = False

    # Routing
    default_policy: str = "balanced"
    use_llm_arbiter: bool = True

    # Surface
    cors_origins: list[str] = ["http://localhost:3000"]
    max_history_messages: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
