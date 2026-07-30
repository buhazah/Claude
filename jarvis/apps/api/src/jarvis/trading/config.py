"""Trading department configuration.

A separate settings object rather than new fields on the kernel's
:class:`~jarvis.config.Settings`: the trading department is optional and
deploys independently of the rest of Jarvis (its own bot token, its own risk
limits), and giving it its own env prefix means enabling it never touches the
kernel's configuration surface.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRADING_", env_file=".env", extra="ignore", case_sensitive=False
    )

    enabled: bool = False

    # Telegram. Without a token the bot cannot poll or send; the department
    # still runs (workflows generate and store signals) so signals can be
    # inspected via the API/database before a bot is ever attached.
    telegram_bot_token: str = ""
    telegram_admin_ids: list[int] = []
    telegram_poll_timeout_s: float = 30.0

    # Market data. Empty provider name means the deterministic simulated
    # provider — the right default for dev, tests, and any deployment that
    # has not yet been pointed at a real vendor.
    market_data_provider: str = "simulated"
    market_data_api_key: str = ""
    options_data_provider: str = "simulated"
    options_data_api_key: str = ""

    # Risk limits (Risk Manager Agent). These are the hard rules with veto
    # power over every signal; they are configuration, not judgement, so a
    # deployment can tighten them without a code change.
    min_probability_of_profit: float = 70.0
    max_risk_per_trade_pct: float = 1.0
    max_daily_signals: int = 3
    max_consecutive_losses: int = 3
    account_size_usd: float = 25_000.0
    economic_event_blackout_hours: float = 24.0
    max_iv_rank_for_entry: float = 95.0
    min_risk_reward_ratio: float = 0.15

    # Workflow cadence.
    market_scan_interval_seconds: float = 300.0
    daily_report_hour_utc: int = 13  # ~08:00 ET, before the open

    # Rate limiting (Telegram command surface).
    rate_limit_per_minute: int = 20


@lru_cache
def get_trading_settings() -> TradingSettings:
    return TradingSettings()
