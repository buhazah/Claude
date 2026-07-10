"""Central configuration for JARVIS, loaded from environment variables.

Every deployable setting lives here so the rest of the codebase never
reads os.environ directly. See docs/ENVIRONMENT.md for the full reference.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("JARVIS_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _secret_key() -> str:
    """Load the signing key, generating and persisting one on first boot.

    A generated key is written to the data directory so restarts do not
    invalidate sessions. Production deployments should set JARVIS_SECRET_KEY.
    """
    env = os.environ.get("JARVIS_SECRET_KEY")
    if env:
        return env
    key_file = DATA_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    key_file.chmod(0o600)
    return key


@dataclass(frozen=True)
class Settings:
    # Core
    app_name: str = "JARVIS"
    version: str = "1.0.0"
    host: str = os.environ.get("JARVIS_HOST", "0.0.0.0")
    # Honor the platform-injected $PORT (Render/Railway/Heroku) when JARVIS_PORT
    # is not explicitly set.
    port: int = int(os.environ.get("JARVIS_PORT") or os.environ.get("PORT") or "8700")
    debug: bool = _bool("JARVIS_DEBUG", False)

    # Persistence
    database_url: str = os.environ.get(
        "JARVIS_DATABASE_URL", f"sqlite+aiosqlite:///{DATA_DIR / 'jarvis.db'}"
    )
    data_dir: Path = DATA_DIR

    # Security
    secret_key: str = field(default_factory=_secret_key)
    access_token_minutes: int = int(os.environ.get("JARVIS_ACCESS_TOKEN_MINUTES", "60"))
    refresh_token_days: int = int(os.environ.get("JARVIS_REFRESH_TOKEN_DAYS", "30"))
    allow_registration: bool = _bool("JARVIS_ALLOW_REGISTRATION", True)
    rate_limit_per_minute: int = int(os.environ.get("JARVIS_RATE_LIMIT_PER_MINUTE", "120"))
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.environ.get("JARVIS_CORS_ORIGINS", "").split(",") if o.strip()
    )

    # Sandbox for filesystem/shell/code tools
    sandbox_dir: Path = Path(os.environ.get("JARVIS_SANDBOX_DIR", DATA_DIR / "sandbox"))
    shell_timeout_seconds: int = int(os.environ.get("JARVIS_SHELL_TIMEOUT", "30"))
    enable_shell_tool: bool = _bool("JARVIS_ENABLE_SHELL_TOOL", True)

    # LLM providers — a provider is active when its key is present
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    google_api_key: str = os.environ.get("GOOGLE_API_KEY", "")
    groq_api_key: str = os.environ.get("GROQ_API_KEY", "")
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "")

    # Embeddings
    embedding_provider: str = os.environ.get("JARVIS_EMBEDDING_PROVIDER", "auto")
    voyage_api_key: str = os.environ.get("VOYAGE_API_KEY", "")

    # Voice
    elevenlabs_api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.environ.get("ELEVENLABS_VOICE_ID", "")
    elevenlabs_model: str = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

    # Search
    search_provider: str = os.environ.get("JARVIS_SEARCH_PROVIDER", "duckduckgo")
    brave_api_key: str = os.environ.get("BRAVE_API_KEY", "")

    # Public base URL, used to build OAuth redirect URIs. If unset it is
    # derived from the incoming request (works behind Render/Railway proxies).
    public_url: str = os.environ.get("JARVIS_PUBLIC_URL", "").rstrip("/")

    # Account integrations (OAuth). A provider is connectable only when its
    # client id/secret are configured. See docs/INTEGRATIONS.md for setup.
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    spotify_client_id: str = os.environ.get("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    # Memory tuning
    memory_decay_half_life_days: float = float(os.environ.get("JARVIS_MEMORY_HALF_LIFE_DAYS", "30"))
    memory_consolidation_threshold: int = int(os.environ.get("JARVIS_MEMORY_CONSOLIDATION_THRESHOLD", "50"))
    memory_max_retrieval: int = int(os.environ.get("JARVIS_MEMORY_MAX_RETRIEVAL", "12"))


settings = Settings()
settings.sandbox_dir.mkdir(parents=True, exist_ok=True)
