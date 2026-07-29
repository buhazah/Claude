from __future__ import annotations

import pytest

from jarvis.config import Settings
from jarvis.kernel import container
from jarvis.kernel.clock import FrozenClock
from jarvis.llm.providers.echo import EchoProvider


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def settings() -> Settings:
    # No keys: the system must be fully exercisable offline.
    # The scheduler is off: time is frozen in tests, and a background loop
    # would fire triggers nobody asked for while assertions are running.
    # Speech is unpaced so the suite stays fast; the tests that actually race
    # an interruption build their own realtime speaker.
    return Settings(
        environment="test",
        use_llm_arbiter=False,
        log_level="WARNING",
        enable_scheduler=False,
        realtime_speech=False,
    )


@pytest.fixture
def jarvis(settings: Settings, clock: FrozenClock) -> container.Jarvis:
    return container.build(settings, providers=[EchoProvider()], clock=clock)
