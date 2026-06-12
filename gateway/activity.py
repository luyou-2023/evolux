"""In-process activity events for dashboard SSE and observability."""

from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActivityEvent:
    kind: str
    session_key: str = ""
    assistant_id: str = ""
    platform: str = ""
    tool: str = ""
    detail: str = ""
    timestamp: str = field(default_factory=_utc_now)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class ActivityBus:
    """Thread-safe pub/sub for runtime activity (gateway turns, tool calls)."""

    def __init__(self, *, history_size: int = 200) -> None:
        self._history: deque[ActivityEvent] = deque(maxlen=history_size)
        self._subscribers: set[asyncio.Queue[ActivityEvent | None]] = set()
        self._lock = threading.Lock()

    def publish(self, event: ActivityEvent) -> None:
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def recent(self, limit: int = 50) -> list[ActivityEvent]:
        with self._lock:
            items = list(self._history)
        return items[-limit:]

    def subscribe(self) -> asyncio.Queue[ActivityEvent | None]:
        queue: asyncio.Queue[ActivityEvent | None] = asyncio.Queue(maxsize=256)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ActivityEvent | None]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def close_subscriber(self, queue: asyncio.Queue[ActivityEvent | None]) -> None:
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        self.unsubscribe(queue)


_BUS = ActivityBus()


def get_activity_bus() -> ActivityBus:
    return _BUS


def emit_activity(kind: str, **fields: Any) -> None:
    _BUS.publish(ActivityEvent(kind=kind, **fields))
