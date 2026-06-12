"""Tool definition resolution — Hermes model_tools alignment."""

from __future__ import annotations

from typing import Any

from toolsets import DELEGATE_BLOCKED_TOOLS, resolve_platform_toolsets, resolve_toolset
from tools.discover import ensure_tools_loaded
from tools.registry import registry


def get_tool_definitions(
    *,
    platform: str = "cli",
    enabled_toolsets: list[str] | None = None,
    extra_tools: list[str] | None = None,
) -> list[dict[str, Any]]:
    ensure_tools_loaded()
    if enabled_toolsets:
        tool_names: set[str] = set()
        for name in enabled_toolsets:
            tool_names |= resolve_toolset(name)
    else:
        tool_names = resolve_platform_toolsets(platform)
    if extra_tools:
        tool_names |= set(extra_tools)
    definitions = registry.get_definitions(tool_names)
    known = {item["function"]["name"] for item in definitions if item.get("function")}
    from tools.orchestrator_tools import get_orchestrator_schemas

    for schema in get_orchestrator_schemas():
        name = schema["function"]["name"]
        if name in tool_names and name not in known:
            definitions.append(schema)
    return definitions


def handle_function_call(name: str, arguments: dict[str, Any] | str, **kwargs: Any) -> str:
    ensure_tools_loaded()
    return registry.dispatch(name, arguments, **kwargs)


def filter_subagent_tools(tool_names: set[str]) -> set[str]:
    return {name for name in tool_names if name not in DELEGATE_BLOCKED_TOOLS}
