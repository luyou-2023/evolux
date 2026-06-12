"""Combine orchestrator and builtin tool dispatch."""

from __future__ import annotations

import json
from typing import Any, Callable

import tools.builtin_tools  # noqa: F401 — register builtins
from tools.orchestrator_tools import OrchestratorToolContext, build_tool_executor
from tools.registry import dispatch as registry_dispatch
from tools.registry import get_schema

ORCHESTRATOR_TOOL_NAMES = frozenset(
    {
        "identify_skills",
        "search_subagents",
        "list_subagents",
        "create_subagent",
        "dispatch_subagent",
        "retire_subagent",
    }
)


def build_combined_tool_executor(
    ctx: OrchestratorToolContext,
    *,
    mcp_router: Any | None = None,
) -> Callable[[dict[str, Any]], str]:
    orchestrator_exec = build_tool_executor(ctx)

    def _executor(tool_call: dict[str, Any]) -> str:
        name = tool_call.get("name", "")
        if name in ORCHESTRATOR_TOOL_NAMES:
            return orchestrator_exec(tool_call)
        if mcp_router is not None and name.startswith("mcp_"):
            arguments = tool_call.get("arguments", {})
            return mcp_router.dispatch(name, arguments)
        if get_schema(name):
            arguments = tool_call.get("arguments", {})
            return registry_dispatch(name, arguments)
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)

    return _executor
