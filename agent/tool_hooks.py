"""Optional hooks for observing tool execution (ACP progress, logging)."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Protocol


class ToolCallHook(Protocol):
    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None: ...

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None: ...


def wrap_tool_executor(
    executor: Callable[[dict[str, Any]], str],
    hook: ToolCallHook | None,
) -> Callable[[dict[str, Any]], str]:
    if hook is None:
        return executor

    def _wrapped(tool_call: dict[str, Any]) -> str:
        name = str(tool_call.get("name", ""))
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, str):
            import json

            arguments = json.loads(arguments) if arguments else {}
        tool_call_id = str(tool_call.get("id") or uuid.uuid4())
        hook.on_tool_start(tool_call_id, name, arguments or {})
        result = executor(tool_call)
        hook.on_tool_end(tool_call_id, name, arguments or {}, result)
        return result

    return _wrapped
