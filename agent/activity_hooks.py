"""Bridge tool hooks to dashboard activity events."""

from __future__ import annotations

import json
from typing import Any

from gateway.activity import emit_activity


class ActivityToolHook:
    def __init__(
        self,
        *,
        session_key: str,
        assistant_id: str,
        platform: str,
    ) -> None:
        self.session_key = session_key
        self.assistant_id = assistant_id
        self.platform = platform

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        emit_activity(
            "tool_start",
            session_key=self.session_key,
            assistant_id=self.assistant_id,
            platform=self.platform,
            tool=name,
            detail=json.dumps(arguments, ensure_ascii=False)[:300],
        )

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        emit_activity(
            "tool_end",
            session_key=self.session_key,
            assistant_id=self.assistant_id,
            platform=self.platform,
            tool=name,
            detail=(result or "")[:300],
        )


class CombinedToolHook:
    def __init__(self, *hooks) -> None:
        self._hooks = [hook for hook in hooks if hook is not None]

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        for hook in self._hooks:
            hook.on_tool_start(tool_call_id, name, arguments)

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        for hook in self._hooks:
            hook.on_tool_end(tool_call_id, name, arguments, result)
