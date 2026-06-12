"""Emit ACP tool call progress updates from orchestrator turns."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import acp
from acp.interfaces import Client

from acp_adapter.tools import build_tool_title, get_tool_kind

logger = logging.getLogger("evolux.acp.progress")


class AcpToolProgressHook:
    """Thread-safe bridge from sync tool executor to async ACP session_update."""

    def __init__(self, *, loop: asyncio.AbstractEventLoop, conn: Client, session_id: str) -> None:
        self._loop = loop
        self._conn = conn
        self._session_id = session_id

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        update = acp.start_tool_call(
            tool_call_id,
            build_tool_title(name, arguments),
            kind=get_tool_kind(name),
            status="in_progress",
            raw_input=arguments,
        )
        self._emit(update)

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        update = acp.update_tool_call(
            tool_call_id,
            title=build_tool_title(name, arguments),
            kind=get_tool_kind(name),
            status="completed",
            raw_input=arguments,
            raw_output=result[:4000],
        )
        self._emit(update)

    def _emit(self, update: Any) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self._conn.session_update(self._session_id, update),
            self._loop,
        )

        def _log_error(fut: asyncio.Future) -> None:
            try:
                fut.result()
            except Exception as exc:
                logger.warning("ACP tool progress update failed: %s", exc)

        future.add_done_callback(_log_error)
