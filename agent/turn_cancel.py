"""Per-session turn cancellation (Hermes /stop)."""

from __future__ import annotations

import threading
from contextvars import ContextVar, Token

_session_key_var: ContextVar[str | None] = ContextVar("evolux_session_key", default=None)
_cancel_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


def bind_session_key(session_key: str) -> Token:
    return _session_key_var.set(session_key)


def unbind_session_key(token: Token) -> None:
    _session_key_var.reset(token)


def clear_turn_cancel(session_key: str) -> None:
    with _lock:
        event = _cancel_events.get(session_key)
        if event is not None:
            event.clear()


def request_turn_cancel(session_key: str) -> None:
    with _lock:
        event = _cancel_events.setdefault(session_key, threading.Event())
    event.set()


def is_turn_cancelled() -> bool:
    session_key = _session_key_var.get()
    if not session_key:
        return False
    with _lock:
        event = _cancel_events.get(session_key)
    return bool(event and event.is_set())
