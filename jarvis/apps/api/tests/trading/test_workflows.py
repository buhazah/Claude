from __future__ import annotations

from jarvis.trading.config import TradingSettings
from jarvis.trading.workflows import (
    DAILY_REPORT_WORKFLOW_ID,
    MARKET_SCAN_WORKFLOW_ID,
    SIGNAL_MONITORING_WORKFLOW_ID,
    daily_report_workflow,
    market_scan_workflow,
    signal_monitoring_workflow,
    trading_triggers,
    trading_workflows,
)


def test_trading_workflows_are_structurally_valid():
    for workflow in trading_workflows():
        assert workflow.validate_graph() == []


def test_market_scan_workflow_chains_collect_then_signal():
    workflow = market_scan_workflow()
    assert workflow.id == MARKET_SCAN_WORKFLOW_ID
    assert [s.tool for s in workflow.steps] == [
        "trading_collect_market_data",
        "trading_generate_signal",
    ]
    assert workflow.steps[-1].terminal is True


def test_daily_report_workflow_has_a_single_terminal_step():
    workflow = daily_report_workflow()
    assert workflow.id == DAILY_REPORT_WORKFLOW_ID
    assert len(workflow.steps) == 1
    assert workflow.steps[0].tool == "trading_daily_report"
    assert workflow.steps[0].terminal is True


def test_signal_monitoring_workflow_chains_monitor_then_performance():
    workflow = signal_monitoring_workflow()
    assert workflow.id == SIGNAL_MONITORING_WORKFLOW_ID
    assert [s.tool for s in workflow.steps] == [
        "trading_monitor_signals",
        "trading_compute_performance",
    ]


def test_trading_triggers_reference_every_workflow_and_use_configured_intervals():
    settings = TradingSettings(
        market_scan_interval_seconds=111.0,
        daily_report_interval_seconds=222.0,
        signal_monitor_interval_seconds=333.0,
    )
    triggers = trading_triggers(settings)
    by_workflow = {t.workflow_id: t for t in triggers}
    assert by_workflow[MARKET_SCAN_WORKFLOW_ID].interval_seconds == 111.0
    assert by_workflow[DAILY_REPORT_WORKFLOW_ID].interval_seconds == 222.0
    assert by_workflow[SIGNAL_MONITORING_WORKFLOW_ID].interval_seconds == 333.0
    assert all(t.enabled for t in triggers)
