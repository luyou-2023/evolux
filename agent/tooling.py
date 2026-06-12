"""Combine orchestrator, Hermes-aligned builtin, and MCP tool dispatch."""

from __future__ import annotations

import json
from typing import Any, Callable

from model_tools import handle_function_call
from toolsets import DELEGATE_BLOCKED_TOOLS
from tools.discover import ensure_tools_loaded
from tools.orchestrator_tools import OrchestratorToolContext, build_tool_executor, get_orchestrator_schemas

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
    assistant_id: str = "default",
    subagent: bool = False,
) -> Callable[[dict[str, Any]], str]:
    ensure_tools_loaded()
    orchestrator_exec = build_tool_executor(ctx)

    def _executor(tool_call: dict[str, Any]) -> str:
        name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments else {}

        if subagent and name in DELEGATE_BLOCKED_TOOLS:
            return json.dumps({"error": f"tool blocked for subagent: {name}"}, ensure_ascii=False)

        if name in ORCHESTRATOR_TOOL_NAMES:
            return orchestrator_exec(tool_call)

        return handle_function_call(name, arguments, assistant_id=assistant_id)

    return _executor


def get_agent_tool_definitions(*, platform: str = "cli", enabled_toolsets: list[str] | None = None) -> list[dict[str, Any]]:
    from model_tools import get_tool_definitions

    ensure_tools_loaded()
    definitions = get_tool_definitions(platform=platform, enabled_toolsets=enabled_toolsets)
    known = {item["function"]["name"] for item in definitions if item.get("function")}
    for schema in get_orchestrator_schemas():
        name = schema["function"]["name"]
        if name not in known:
            definitions.append(schema)
    return definitions
