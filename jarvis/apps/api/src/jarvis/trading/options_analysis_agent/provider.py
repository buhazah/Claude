"""SPX options chain sources: a deterministic simulated chain for dev/tests,
and the seam for a real vendor (CBOE, Tradier, Polygon)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

STRIKE_STEP = 25.0
STRIKE_RANGE = 500.0
DEFAULT_EXPIRATIONS_DTE = (7, 14, 21, 30, 45)
IV_HISTORY_DAYS = 252


@dataclass(slots=True, frozen=True)
class RawOptionQuote:
    strike: float
    option_type: str  # "call" | "put"
    expiration: str  # ISO date
    days_to_expiration: int
    implied_volatility: float
    open_interest: int
    volume: int


@dataclass(slots=True)
class RawOptionsChain:
    underlying: str
    spot: float
    timestamp: datetime
    quotes: list[RawOptionQuote]
    iv_history: list[float] = field(default_factory=list)
    risk_free_rate: float = 0.05

    def at_expiration(self, expiration: str) -> list[RawOptionQuote]:
        return [q for q in self.quotes if q.expiration == expiration]

    def expirations(self) -> list[str]:
        seen: dict[str, int] = {}
        for q in self.quotes:
            seen.setdefault(q.expiration, q.days_to_expiration)
        return sorted(seen, key=lambda e: seen[e])


class OptionsDataProvider(Protocol):
    async def fetch_chain(
        self, *, underlying: str, spot: float, now: datetime
    ) -> RawOptionsChain: ...


class SimulatedOptionsDataProvider:
    """A deterministic synthetic SPX chain with a realistic volatility smile."""

    def __init__(self, *, base_iv: float = 0.14, seed: int = 0) -> None:
        self._base_iv = base_iv
        self._seed = seed

    def _iv_for(self, rng: random.Random, moneyness: float, wave: float) -> float:
        smile = abs(moneyness) * 0.55  # further OTM/ITM carries more IV
        return max(0.03, self._base_iv + wave + smile + rng.uniform(-0.005, 0.005))

    async def fetch_chain(self, *, underlying: str, spot: float, now: datetime) -> RawOptionsChain:
        minute_bucket = int(now.timestamp() // 60)
        rng = random.Random((minute_bucket * 40503 + self._seed) & 0xFFFFFFFF)
        wave = math.sin(minute_bucket / 240.0) * 0.03

        lowest_strike = round((spot - STRIKE_RANGE) / STRIKE_STEP) * STRIKE_STEP
        highest_strike = round((spot + STRIKE_RANGE) / STRIKE_STEP) * STRIKE_STEP
        strikes = []
        strike = lowest_strike
        while strike <= highest_strike:
            strikes.append(strike)
            strike += STRIKE_STEP

        quotes: list[RawOptionQuote] = []
        for dte in DEFAULT_EXPIRATIONS_DTE:
            expiration = (now + timedelta(days=dte)).date().isoformat()
            for k in strikes:
                moneyness = (k - spot) / spot
                distance = abs(k - spot)
                liquidity_decay = max(0.02, math.exp(-distance / 150.0))
                for option_type in ("call", "put"):
                    iv = self._iv_for(rng, moneyness, wave)
                    oi = int(15_000 * liquidity_decay * rng.uniform(0.6, 1.4))
                    volume = int(3_000 * liquidity_decay * rng.uniform(0.4, 1.6))
                    quotes.append(
                        RawOptionQuote(
                            strike=k,
                            option_type=option_type,
                            expiration=expiration,
                            days_to_expiration=dte,
                            implied_volatility=round(iv, 4),
                            open_interest=oi,
                            volume=volume,
                        )
                    )

        iv_history = [
            max(0.03, self._base_iv + math.sin(day / 20.0) * 0.04 + rng.uniform(-0.01, 0.01))
            for day in range(IV_HISTORY_DAYS)
        ]

        return RawOptionsChain(
            underlying=underlying,
            spot=spot,
            timestamp=now,
            quotes=quotes,
            iv_history=iv_history,
        )
