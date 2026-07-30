"""The three automation workflows, built on the kernel's existing workflow
engine, triggers and scheduler — no bespoke scheduling code for trading.

Jarvis's :class:`~jarvis.workflows.triggers.Scheduler` fires on a fixed
interval rather than a time-of-day cron, so the Daily Report's "before market
open" is approximated by a ~24h cadence rather than a guaranteed clock time;
see :class:`~jarvis.trading.config.TradingSettings` for the note on what a
real deployment does about that.
"""

from __future__ import annotations

from jarvis.trading.config import TradingSettings
from jarvis.workflows.models import StepKind, Trigger, TriggerKind, Workflow, WorkflowStep

MARKET_SCAN_WORKFLOW_ID = "wfl_trading_market_scan"
DAILY_REPORT_WORKFLOW_ID = "wfl_trading_daily_report"
SIGNAL_MONITORING_WORKFLOW_ID = "wfl_trading_signal_monitoring"


def market_scan_workflow() -> Workflow:
    return Workflow(
        id=MARKET_SCAN_WORKFLOW_ID,
        name="Market Scan",
        description=(
            "Collect data → analyze market → analyze options → generate "
            "strategies → risk approval → create signal."
        ),
        steps=[
            WorkflowStep(
                id="collect",
                kind=StepKind.TOOL,
                label="Collect market and options data",
                tool="trading_collect_market_data",
            ),
            WorkflowStep(
                id="signal",
                kind=StepKind.TOOL,
                label="Analyse, propose, risk-check and publish",
                tool="trading_generate_signal",
                terminal=True,
            ),
        ],
    )


def daily_report_workflow() -> Workflow:
    return Workflow(
        id=DAILY_REPORT_WORKFLOW_ID,
        name="Daily Report",
        description=(
            "Market overview, SPX levels, expected volatility and positioning, before the open."
        ),
        steps=[
            WorkflowStep(
                id="report",
                kind=StepKind.TOOL,
                label="Compose and broadcast the daily report",
                tool="trading_daily_report",
                terminal=True,
            ),
        ],
    )


def signal_monitoring_workflow() -> Workflow:
    return Workflow(
        id=SIGNAL_MONITORING_WORKFLOW_ID,
        name="Signal Monitoring",
        description=(
            "Track every published signal for target, stop or expiration, "
            "settle it, then recompute performance."
        ),
        steps=[
            WorkflowStep(
                id="monitor",
                kind=StepKind.TOOL,
                label="Check active signals for target, stop or expiration",
                tool="trading_monitor_signals",
            ),
            WorkflowStep(
                id="performance",
                kind=StepKind.TOOL,
                label="Recompute performance metrics",
                tool="trading_compute_performance",
                terminal=True,
            ),
        ],
    )


def trading_workflows() -> list[Workflow]:
    return [market_scan_workflow(), daily_report_workflow(), signal_monitoring_workflow()]


def trading_triggers(settings: TradingSettings) -> list[Trigger]:
    return [
        Trigger(
            workflow_id=MARKET_SCAN_WORKFLOW_ID,
            kind=TriggerKind.SCHEDULE,
            interval_seconds=settings.market_scan_interval_seconds,
        ),
        Trigger(
            workflow_id=DAILY_REPORT_WORKFLOW_ID,
            kind=TriggerKind.SCHEDULE,
            interval_seconds=settings.daily_report_interval_seconds,
        ),
        Trigger(
            workflow_id=SIGNAL_MONITORING_WORKFLOW_ID,
            kind=TriggerKind.SCHEDULE,
            interval_seconds=settings.signal_monitor_interval_seconds,
        ),
    ]
