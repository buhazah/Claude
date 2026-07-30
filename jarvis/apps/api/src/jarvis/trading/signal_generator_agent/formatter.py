"""Renders a :class:`~jarvis.trading.models.Signal` as the Telegram message
subscribers actually see."""

from __future__ import annotations

from datetime import date

from jarvis.trading.models import Signal, StrategyType, Trend

_DIRECTION_DISPLAY: dict[Trend, tuple[str, str]] = {
    Trend.BULLISH: ("Bullish", "\U0001f7e2"),
    Trend.BEARISH: ("Bearish", "\U0001f534"),
    Trend.NEUTRAL: ("Neutral", "⚪"),
}


def _strategy_label(strategy_type: StrategyType) -> str:
    return strategy_type.value.replace("_", " ").title()


def _format_expiration(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d %b").upper()


def render_signal_message(signal: Signal) -> str:
    strategy = signal.strategy
    direction_label, emoji = _DIRECTION_DISPLAY[signal.market_direction]

    lines = [
        "================================",
        "",
        "\U0001f916 HERMES SPX AI SIGNAL",
        "",
        "Market Direction:",
        f"{emoji} {direction_label}",
        "",
        "Strategy:",
        _strategy_label(strategy.strategy_type),
        "",
    ]

    for leg in strategy.legs:
        quantity = f" x{leg.quantity}" if leg.quantity > 1 else ""
        lines.append(f"{leg.action.upper()}:")
        lines.append(f"SPX {leg.strike:.0f} {leg.option_type.capitalize()}{quantity}")
        lines.append("")

    lines += ["Expiration:", _format_expiration(strategy.expiration), ""]
    if strategy.is_credit:
        lines += ["Credit:", f"${strategy.credit:.2f}", ""]
    else:
        lines += ["Debit:", f"${strategy.debit:.2f}", ""]

    lines += [
        "Max Risk:",
        f"${strategy.max_loss:.0f}",
        "",
        "Probability:",
        f"{strategy.probability_of_profit:.0f}%",
        "",
        "Confidence:",
        f"{signal.confidence}/10",
        "",
        "Reason:",
        "",
        *[f"- {reason}" for reason in signal.reasons],
        "",
        "Risk Level:",
        signal.risk_level.value.capitalize(),
        "",
        "================================",
    ]
    return "\n".join(lines)
