# Trading — Hermes SPX AI Signal Bot

An SPX options AI Telegram signal bot, built as a new department on the
existing Jarvis kernel — the event bus, workflow engine, scheduler, tool
registry, memory, security and observability are all reused, not
reimplemented. Nothing in this department is a chat agent: market data
collection, technical and options analysis, strategy construction and risk
filtering are deterministic computation, because a trading system needs the
same input to always produce the same output.

> **A note on the name.** The brief that specified this department called
> it an extension of "Hermes." No such system exists in this repository —
> the closest match to the described architecture (Central Orchestrator,
> Agent Workers, Event Bus, Workflow Engine, Memory System, Observability,
> Security Layer) is Jarvis, which already has exactly those components. This
> department extends Jarvis; "Hermes SPX AI Signal Bot" is the product name
> shown to Telegram subscribers.

> **This is a decision-support and paper-trading system, not a broker
> integration.** It generates signals and tracks their outcomes against
> market data; it never places a real order. Treat every signal as
> informational. Options trading carries substantial risk of loss.

## Architecture

```
trading/
├── market_data_agent/       SPX/SPY/VIX/futures/breadth collection
├── technical_analysis_agent/ SMA/EMA/RSI/MACD/VWAP, support/resistance
├── options_analysis_agent/  Black-Scholes greeks, IV rank, expected move
├── strategy_agent/          6 strategy builders, priced off the chain
├── risk_manager_agent/      7 hard rules with veto power
├── signal_generator_agent/  Telegram message + Signal record
├── performance_agent/       win rate, drawdown, per-strategy breakdown
├── telegram_agent/          Bot API client, commands, rate limiting
├── database/                7 tables, in-memory + SQL stores
├── monitoring.py            expiration settlement, target/stop rules
├── workflows.py             the 3 automation workflows + triggers
├── tools.py                 registers the pipeline as Jarvis tools
├── bootstrap.py             composition root: install_trading(jarvis)
└── config.py                TradingSettings (env: TRADING_*)
```

Each agent is a plain Python class with a pure `analyze`/`generate`/
`evaluate` method — unit-tested without a market open anywhere. `tools.py`
is the only place that wires them into Jarvis's `ToolRegistry`, and each
tool re-derives its input from the durable `TradingStore` rather than from
a previous workflow step's raw output: the pipeline's intermediate values
(a `TechnicalAnalysis`, a list of candidate `Strategy` objects, a
`RiskDecision`) are typed Pydantic models, and Jarvis's workflow engine
passes step-to-step data through a string-templated JSON context built for
chaining LLM agent turns, not for round-tripping nested objects. A tool that
reads current state and writes new state is also idempotent, which a step
in an automated, scheduled pipeline should be regardless of what triggered it.

## The pipeline

1. **Market Data Agent** collects SPX/SPY/VIX/futures/breadth/calendar/
   sentiment into a `MarketSnapshot`.
2. **Technical Analysis Agent** reads a price history and produces trend,
   strength, confidence, moving averages, RSI, MACD, VWAP and support/
   resistance levels.
3. **Options Analysis Agent** reads the SPX chain and produces IV, IV rank,
   volatility state, expected move, positioning and the most important
   strikes with their Black-Scholes greeks.
4. **Strategy Agent** proposes every strategy allowed for the current trend
   (bull put/call spreads, bear call/put spreads, iron condor, butterfly),
   each fully priced — credit/debit, max profit/loss, probability of
   profit, risk/reward — before risk ever sees it.
5. **Risk Manager Agent** runs seven independent checks (probability of
   profit, risk per trade vs. account size, daily signal cap,
   consecutive-loss halt, economic-event blackout, volatility ceiling,
   risk/reward floor). All must pass. A rejection reports *every* failing
   rule, not just the first.
6. **Signal Generator Agent** renders the approved strategy into the
   `🤖 HERMES SPX AI SIGNAL` Telegram message and a `Signal` record.
7. **Telegram Agent** publishes it to every subscriber with notifications
   on, and serves `/start /signal /market /history /performance /settings
   /admin`.
8. **Performance Agent** and the Signal Monitoring workflow settle expired
   signals against intrinsic value, apply a systematic target/stop rule to
   open ones, and recompute win rate, average return, drawdown and
   per-strategy performance.

## Workflows

Three `jarvis.workflows.Workflow` objects, each on a `SCHEDULE` trigger,
registered by `install_trading`:

| Workflow | Steps | Default cadence |
|---|---|---|
| Market Scan | collect → analyse → propose → risk-check → publish | every 5 min |
| Daily Report | compose and broadcast a market overview | ~daily |
| Signal Monitoring | check target/stop/expiration → settle → recompute performance | every 5 min |

Jarvis's scheduler fires on a fixed interval, not a time-of-day cron, so
"before market open" for the Daily Report is approximated by a ~24h cadence
anchored to whenever the trigger was created. A deployment that needs a
guaranteed wall-clock time schedules the *process* (e.g. a cron-triggered
restart, or a future cron-capable trigger kind) rather than relying on the
interval alone.

## Enabling it

Off by default (`TRADING_ENABLED=false`). Turned on, `jarvis.main`'s
lifespan calls `install_trading(jarvis)` after the kernel starts: it
registers the five trading tools, saves the three workflows and their
triggers into the same workflow store Jarvis already has, and — if a bot
token is configured — starts the Telegram long-poll loop as a background
task in the same process. No second service is required; the scheduler
already running inside the API process drives the workflows.

```bash
export TRADING_ENABLED=true
export TRADING_TELEGRAM_BOT_TOKEN=...           # from @BotFather
export TRADING_TELEGRAM_ADMIN_IDS='[123456789]' # Telegram user ids, /admin access
uvicorn jarvis.main:app --host 0.0.0.0 --port 8000
```

Or with the provided stack:

```bash
TRADING_ENABLED=true TRADING_TELEGRAM_BOT_TOKEN=... docker compose up
```

## Market and options data

`TRADING_MARKET_DATA_PROVIDER` and `TRADING_OPTIONS_DATA_PROVIDER` default
to `simulated`: a deterministic synthetic feed (`SimulatedMarketDataProvider`,
`SimulatedOptionsDataProvider`) used by every test and by any deployment
that has not yet been pointed at a real vendor. It is a pure function of
the timestamp — the same minute always produces the same reading — so the
whole pipeline is explorable and testable with no market open and no API
key anywhere.

To point at a real vendor:

- **Market data**: implement `MarketDataProvider` (see
  `market_data_agent/provider.py`) or configure the bundled
  `HttpMarketDataProvider` against a REST endpoint that returns the fields
  it expects, via `TRADING_MARKET_DATA_BASE_URL` and
  `TRADING_MARKET_DATA_API_KEY`.
- **Options data**: implement `OptionsDataProvider` (see
  `options_analysis_agent/provider.py`) for your vendor's chain format —
  CBOE, Tradier and Polygon all shape a chain differently enough that no
  generic HTTP adapter is bundled — and wire it in
  `bootstrap.build_options_data_provider`.

## Risk configuration

All hard limits the Risk Manager Agent enforces are configuration, not
judgement, so a deployment can tighten them without a code change:

| Setting | Default | Meaning |
|---|---|---|
| `TRADING_MIN_PROBABILITY_OF_PROFIT` | `70.0` | minimum POP to approve |
| `TRADING_MAX_RISK_PER_TRADE_PCT` | `1.0` | max loss as % of account |
| `TRADING_MAX_DAILY_SIGNALS` | `3` | signals per day |
| `TRADING_MAX_CONSECUTIVE_LOSSES` | `3` | halts new signals at this streak |
| `TRADING_ACCOUNT_SIZE_USD` | `25000.0` | basis for the risk-per-trade check |
| `TRADING_MAX_IV_RANK_FOR_ENTRY` | `95.0` | rejects extreme-IV entries |
| `TRADING_MIN_RISK_REWARD_RATIO` | `0.15` | rejects poor risk/reward |
| `TRADING_TARGET_PROFIT_WIDTH_FRACTION` | `0.5` | early-exit target, fraction of spread width |
| `TRADING_STOP_LOSS_WIDTH_FRACTION` | `0.5` | early-exit stop, fraction of spread width |

See `config.py` for the complete list, including workflow cadence and rate
limiting.

## Security

- **User auth / admin roles**: a Telegram user becomes a subscriber on
  `/start`; `TRADING_TELEGRAM_ADMIN_IDS` grants `/admin` access.
- **Rate limiting**: a per-user fixed-window limiter
  (`TRADING_RATE_LIMIT_PER_MINUTE`) on the command surface.
- **API keys**: loaded from environment variables, following the same
  convention as every other Jarvis credential; never logged (structlog
  fields are the tool name and outcome, not payloads containing secrets).
- **Audit trail**: `trading_generate_signal`, `trading_daily_report` and
  `trading_monitor_signals` are registered at `Permission.SENSITIVE`, so
  every invocation is written to Jarvis's existing append-only audit log
  automatically — no separate audit mechanism for trading.

## Database

Seven tables (`trading_users`, `trading_signals`, `trading_market_snapshots`,
`trading_options_snapshots`, `trading_trade_results`,
`trading_performance_metrics`, `trading_subscriptions`) on Jarvis's existing
`Base`/`Database`/Alembic setup — one schema, one migration history.
`InMemoryTradingStore` backs local dev and every test; `SqlTradingStore`
backs SQLite (local-first) or Postgres (`JARVIS_DATABASE_URL`), the same
switch every other Jarvis store uses.

## Testing

```bash
cd apps/api && .venv/bin/python -m pytest tests/trading -q
```

259 tests: pure-function coverage for every indicator, every greek, every
strategy builder and every risk rule; store-contract tests run against both
backends; a full pipeline integration test through `TradingTools`; the
Telegram command surface and rate limiter with no network; and the whole
department wired through the real ASGI lifespan with `TRADING_ENABLED`.
`ruff check`, `ruff format --check` and `mypy --strict` are clean for the
whole department.

## What is intentionally not here

- **Real order execution.** This system never talks to a broker. Turning
  results into real trades is a deliberately separate, much higher-stakes
  integration this department does not attempt.
- **A cron-precision daily report time.** See "Workflows" above.
- **A bundled real market-data/options vendor adapter.** See "Market and
  options data" above — the seam is a two-method protocol; the adapter is
  vendor-specific and not included.
