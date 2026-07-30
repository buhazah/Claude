from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jarvis.kernel.clock import FrozenClock


@pytest.fixture
def trading_clock() -> FrozenClock:
    # A Tuesday, mid-session, away from the synthetic FOMC/NFP event windows.
    return FrozenClock(datetime(2026, 3, 10, 16, 30, tzinfo=UTC))
