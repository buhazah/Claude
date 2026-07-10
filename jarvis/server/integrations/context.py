"""Per-execution user context.

Tools run as plain functions without an explicit user argument, but
account-connected tools (calendar, spotify, gmail) need to know *whose*
tokens to use. The agent runtime sets this contextvar before running, and
connected tools read it. Uses contextvars so concurrent requests stay
isolated.
"""
from __future__ import annotations

import contextvars

_current_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "jarvis_current_user_id", default=None
)


def set_current_user(user_id: str | None):
    return _current_user_id.set(user_id)


def reset_current_user(token) -> None:
    _current_user_id.reset(token)


def get_current_user_id() -> str | None:
    return _current_user_id.get()
