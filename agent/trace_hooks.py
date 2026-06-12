"""Collect orchestration trace for CLI and Feishu surfaces."""

from __future__ import annotations

from typing import Any

from agent.turn_trace import TurnTrace


class TraceToolHook:
    def __init__(self, trace: TurnTrace, *, agent_id: str = "") -> None:
        self.trace = trace
        self.agent_id = agent_id

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        return

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        self.trace.add_tool(
            name=name,
            arguments=arguments,
            result=result,
            agent_id=self.agent_id,
        )
