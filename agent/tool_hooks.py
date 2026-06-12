"""Optional hooks for observing tool execution (ACP progress, logging)."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Protocol

from agent.tool_calls import parse_tool_call


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
        name, arguments = parse_tool_call(tool_call)
        tool_call_id = str(tool_call.get("id") or uuid.uuid4())
        hook.on_tool_start(tool_call_id, name, arguments)
        result = executor({"id": tool_call_id, "name": name, "arguments": arguments})
        hook.on_tool_end(tool_call_id, name, arguments, result)
        return result

    return _wrapped
