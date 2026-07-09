"""Tests for the cron parser and scheduler helpers."""
from datetime import datetime

from server.automation.scheduler import cron_matches, next_run_after


def test_cron_every_minute():
    assert cron_matches("* * * * *", datetime(2026, 7, 9, 12, 30))


def test_cron_specific_time():
    assert cron_matches("0 9 * * *", datetime(2026, 7, 9, 9, 0))
    assert not cron_matches("0 9 * * *", datetime(2026, 7, 9, 9, 1))
    assert not cron_matches("0 9 * * *", datetime(2026, 7, 9, 10, 0))


def test_cron_step_and_range():
    # Every 15 minutes
    assert cron_matches("*/15 * * * *", datetime(2026, 7, 9, 8, 15))
    assert not cron_matches("*/15 * * * *", datetime(2026, 7, 9, 8, 16))
    # Business hours range
    assert cron_matches("0 9-17 * * *", datetime(2026, 7, 9, 13, 0))
    assert not cron_matches("0 9-17 * * *", datetime(2026, 7, 9, 18, 0))


def test_cron_list():
    assert cron_matches("0 8,12,18 * * *", datetime(2026, 7, 9, 12, 0))
    assert not cron_matches("0 8,12,18 * * *", datetime(2026, 7, 9, 15, 0))


def test_next_run_after():
    nxt = next_run_after("0 9 * * *", datetime(2026, 7, 9, 10, 0))
    assert nxt == datetime(2026, 7, 10, 9, 0)


def test_next_run_manual_is_none():
    assert next_run_after("manual", datetime(2026, 7, 9, 10, 0)) is None


def test_db_url_normalization_for_paas():
    from server.db import _normalize_db_url as n

    assert n("postgres://u:p@h:5432/db") == "postgresql+asyncpg://u:p@h:5432/db"
    # libpq-only query params asyncpg rejects are stripped
    assert n("postgresql://u:p@h/db?sslmode=require") == "postgresql+asyncpg://u:p@h/db"
    assert (
        n("postgresql://u:p@h/db?sslmode=require&application_name=x")
        == "postgresql+asyncpg://u:p@h/db?application_name=x"
    )
    # SQLite is left untouched
    assert n("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"
