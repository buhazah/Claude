"""Configuration. Environment-driven, validated once at boot."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fields whose value goes into an HTTP header or an auth exchange. A key
# carrying a stray newline is the single most common way a correct key fails,
# because the shell that set it kept the trailing character from a copy-paste.
CREDENTIAL_FIELDS = (
    "anthropic_api_key",
    "openai_api_key",
    "embedding_api_key",
    "speech_api_key",
    "vault_key",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JARVIS_", env_file=".env", extra="ignore", case_sensitive=False
    )

    @field_validator(*CREDENTIAL_FIELDS, mode="before")
    @classmethod
    def _strip_credential(cls, value: Any) -> Any:
        """Trim whitespace from anything used as a credential.

        httpx rejects a header value containing a newline with "Illegal header
        value", which names the symptom and not the cause — so the user sees a
        transport error and reasonably concludes their key is wrong. Stripping
        here fixes it once for every provider rather than in each adapter, and
        an API key with meaningful leading or trailing whitespace does not
        exist.
        """
        return value.strip() if isinstance(value, str) else value

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

    # Workflows. The scheduler is off in tests, where time is frozen and a
    # background loop would fire triggers nobody asked for.
    enable_scheduler: bool = True

    # Voice. Without a key, speech recognition happens in the browser and
    # synthesis is silent — the session logic is identical either way.
    speech_api_key: str | None = None
    speech_base_url: str = "https://api.openai.com/v1"
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    wake_word: str = "jarvis"
    require_wake_word: bool = False
    # The offline speaker plays silence, but it plays it *at speaking pace*.
    # Without that a turn finishes in milliseconds and nobody — user or test —
    # can ever talk over Jarvis, which is the whole point of voice mode. Tests
    # that only care about the transcript turn this off to stay fast.
    realtime_speech: bool = True

    # Computer control. Off unless asked for: a browser Jarvis can drive is a
    # capability, and capabilities should be opted into rather than discovered.
    enable_computer: bool = False
    browser_headless: bool = True
    browser_executable: str = ""
    # Hosts Jarvis may open unattended. Everything else is escalated to an
    # approval rather than blocked — an agent doing research legitimately needs
    # somewhere new, and that is also exactly what an injection asks for.
    browser_allowed_hosts: list[str] = []
    browser_blocked_hosts: list[str] = []
    browser_max_steps: int = 40
    browser_max_seconds: float = 300.0

    # Secrets. Without a key the vault is locked: nothing can be stored and
    # nothing can be read, which is the right default — a vault that silently
    # keeps plaintext because it was misconfigured is worse than no vault.
    # Generate one with `python -m jarvis.security.keygen`.
    vault_key: str = ""

    # Cost governance. Zero means unenforced. The soft ceiling asks a human;
    # the hard ceiling refuses, because the case a hard ceiling exists for is
    # the one where approval requests are arriving faster than anyone reads.
    daily_budget_soft_usd: float = 0.0
    daily_budget_hard_usd: float = 0.0
    monthly_budget_soft_usd: float = 0.0
    monthly_budget_hard_usd: float = 0.0

    # Routing
    default_policy: str = "balanced"
    use_llm_arbiter: bool = True

    # Surface
    cors_origins: list[str] = ["http://localhost:3000"]
    max_history_messages: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
