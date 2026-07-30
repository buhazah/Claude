from __future__ import annotations

from jarvis.kernel.clock import FrozenClock
from jarvis.trading.telegram_agent.ratelimit import RateLimiter


def test_allows_up_to_the_configured_limit():
    clock = FrozenClock()
    limiter = RateLimiter(max_per_minute=3, clock=clock)
    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is False


def test_tracks_each_user_independently():
    clock = FrozenClock()
    limiter = RateLimiter(max_per_minute=1, clock=clock)
    assert limiter.allow(1) is True
    assert limiter.allow(2) is True
    assert limiter.allow(1) is False
    assert limiter.allow(2) is False


def test_window_resets_after_sixty_seconds():
    clock = FrozenClock()
    limiter = RateLimiter(max_per_minute=1, clock=clock)
    assert limiter.allow(1) is True
    assert limiter.allow(1) is False
    clock.advance(61)
    assert limiter.allow(1) is True
