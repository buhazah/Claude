"""Composition root for the trading department.

Takes an already-built :class:`~jarvis.kernel.container.Jarvis` — the event
bus, tool registry, workflow store and (optionally) database it already
has — and adds trading on top, rather than folding trading into
``jarvis.kernel.container.build()`` itself. The department is optional and
deploys independently (its own bot token, its own risk limits); a caller
that never imports this module gets a Jarvis with no trading footprint at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from jarvis.kernel.container import Jarvis
from jarvis.trading.config import TradingSettings, get_trading_settings
from jarvis.trading.database.store import InMemoryTradingStore, SqlTradingStore, TradingStore
from jarvis.trading.market_data_agent.agent import MarketDataAgent
from jarvis.trading.market_data_agent.provider import (
    HttpMarketDataProvider,
    MarketDataProvider,
    SimulatedMarketDataProvider,
)
from jarvis.trading.options_analysis_agent.agent import OptionsAnalysisAgent
from jarvis.trading.options_analysis_agent.provider import (
    OptionsDataProvider,
    SimulatedOptionsDataProvider,
)
from jarvis.trading.performance_agent.agent import PerformanceAgent
from jarvis.trading.risk_manager_agent.agent import RiskManagerAgent
from jarvis.trading.signal_generator_agent.agent import SignalGeneratorAgent
from jarvis.trading.strategy_agent.agent import StrategyAgent
from jarvis.trading.technical_analysis_agent.agent import TechnicalAnalysisAgent
from jarvis.trading.telegram_agent.bot import TelegramBot
from jarvis.trading.telegram_agent.client import TelegramClient
from jarvis.trading.tools import TradingTools, register_trading_tools
from jarvis.trading.workflows import trading_triggers, trading_workflows

log = structlog.get_logger(__name__)


def build_market_data_provider(settings: TradingSettings) -> MarketDataProvider:
    if settings.market_data_provider != "simulated" and settings.market_data_api_key:
        return HttpMarketDataProvider(
            base_url=settings.market_data_base_url, api_key=settings.market_data_api_key
        )
    return SimulatedMarketDataProvider()


def build_options_data_provider(settings: TradingSettings) -> OptionsDataProvider:
    # A real vendor (CBOE, Tradier, Polygon) implements the OptionsDataProvider
    # protocol and is wired in here; none is bundled because chain formats are
    # vendor-specific in a way a generic HTTP adapter cannot paper over.
    return SimulatedOptionsDataProvider()


@dataclass(slots=True)
class TradingDepartment:
    settings: TradingSettings
    store: TradingStore
    tools: TradingTools
    telegram_bot: TelegramBot | None


async def install_trading(
    jarvis: Jarvis, settings: TradingSettings | None = None
) -> TradingDepartment | None:
    """Wire the trading department into an already-built Jarvis. Returns
    ``None`` (and touches nothing) unless ``TRADING_ENABLED=true``."""
    settings = settings or get_trading_settings()
    if not settings.enabled:
        log.info("trading_department_disabled")
        return None

    store: TradingStore = (
        SqlTradingStore(jarvis.database) if jarvis.database is not None else InMemoryTradingStore()
    )

    market_data_provider = build_market_data_provider(settings)
    options_data_provider = build_options_data_provider(settings)

    telegram_bot: TelegramBot | None = None
    if settings.telegram_bot_token:
        telegram_bot = TelegramBot(
            client=TelegramClient(settings.telegram_bot_token),
            store=store,
            settings=settings,
        )

    tools = TradingTools(
        settings=settings,
        store=store,
        market_data_provider=market_data_provider,
        options_data_provider=options_data_provider,
        market_data_agent=MarketDataAgent(market_data_provider),
        technical_agent=TechnicalAnalysisAgent(),
        options_agent=OptionsAnalysisAgent(),
        strategy_agent=StrategyAgent(),
        risk_agent=RiskManagerAgent(settings),
        signal_agent=SignalGeneratorAgent(),
        performance_agent=PerformanceAgent(account_size_usd=settings.account_size_usd),
        telegram_bot=telegram_bot,
    )
    register_trading_tools(jarvis.tools, tools)

    for workflow in trading_workflows():
        await jarvis.workflows.save(workflow)
    for trigger in trading_triggers(settings):
        await jarvis.workflows.save_trigger(trigger)

    log.info(
        "trading_department_installed",
        storage=type(store).__name__,
        telegram=telegram_bot is not None,
    )
    return TradingDepartment(settings=settings, store=store, tools=tools, telegram_bot=telegram_bot)
