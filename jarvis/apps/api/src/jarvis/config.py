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

    # Persistence. Empty means fully in-process — no file, no server, which is
    # what tests and a first run get. "sqlite+aiosqlite:///jarvis.db" is the
    # local-first default for a real install; a postgresql:// url is the server.
    database_url: str = ""
    database_echo: bool = False

    # Distributed event bus. Empty means in-process only, which is correct
    # until Jarvis runs more than one worker.
    redis_url: str = ""

    # Embeddings. Without a key, the deterministic local embedder is used.
    embedding_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://api.openai.com/v1"

    # Tools. The workspace is the boundary filesystem and shell tools operate
    # inside; approvals expire into denial, never into consent.
    workspace_dir: str = "~/.jarvis/workspace"
    approval_timeout_s: float = 300.0
    # JSON list of MCP servers, e.g.
    # [{"name":"github","command":["npx","-y","@modelcontextprotocol/server-github"]}]
    mcp_servers: str = ""

    # Routing
    default_policy: str = "balanced"
    use_llm_arbiter: bool = True

    # Surface
    cors_origins: list[str] = ["http://localhost:3000"]
    max_history_messages: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
