"""A per-user fixed-window rate limiter for the command surface.

Fixed-window rather than a sliding log: a Telegram bot's abuse case is a
user hammering commands, not a precise quota, so counting hits in the
trailing 60 seconds and evicting stale ones is enough — and it is O(hits),
not O(1), so it never needs a background sweep.
"""

from __future__ import annotations

from jarvis.kernel.clock import SYSTEM_CLOCK, Clock

WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, *, max_per_minute: int, clock: Clock = SYSTEM_CLOCK) -> None:
        self._max = max_per_minute
        self._clock = clock
        self._hits: dict[int, list[float]] = {}

    def allow(self, telegram_id: int) -> bool:
        now = self._clock.monotonic()
        cutoff = now - WINDOW_SECONDS
        recent = [t for t in self._hits.get(telegram_id, []) if t >= cutoff]
        if len(recent) >= self._max:
            self._hits[telegram_id] = recent
            return False
        recent.append(now)
        self._hits[telegram_id] = recent
        return True
