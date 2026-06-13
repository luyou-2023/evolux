"""Tool definition resolution — Hermes model_tools alignment."""

from __future__ import annotations

from typing import Any

from toolsets import DELEGATE_BLOCKED_TOOLS, resolve_platform_toolsets, resolve_toolset
from tools.discover import ensure_tools_loaded
from tools.registry import registry


def _mcp_tool_names() -> set[str]:
    return set(registry.list_names(toolset_prefix="mcp-"))


def apply_mcp_allowlist(tool_names: set[str], mcp_servers: list[str] | None) -> set[str]:
    """Filter MCP-prefixed tools. ``None`` keeps all MCP tools already in *tool_names*."""
    if mcp_servers is None:
        return tool_names
    if not mcp_servers:
        return {name for name in tool_names if not name.startswith("mcp_")}
    prefixes = tuple(f"mcp_{server}_" for server in mcp_servers)
    return {
        name
        for name in tool_names
        if not name.startswith("mcp_") or name.startswith(prefixes)
    }


def get_tool_definitions(
    *,
    platform: str = "cli",
    enabled_toolsets: list[str] | None = None,
    extra_tools: list[str] | None = None,
    include_mcp: bool = True,
    mcp_servers: list[str] | None = None,
) -> list[dict[str, Any]]:
    ensure_tools_loaded()
    if enabled_toolsets:
        tool_names: set[str] = set()
        for name in enabled_toolsets:
            tool_names |= resolve_toolset(name)
    else:
        tool_names = resolve_platform_toolsets(platform)
    if platform == "cron":
        tool_names.discard("cronjob")
    if extra_tools:
        tool_names |= set(extra_tools)
    if include_mcp:
        tool_names |= _mcp_tool_names()
    tool_names = apply_mcp_allowlist(tool_names, mcp_servers)
    definitions = registry.get_definitions(tool_names)
    known = {item["function"]["name"] for item in definitions if item.get("function")}
    from tools.orchestrator_tools import get_orchestrator_schemas

    for schema in get_orchestrator_schemas():
        name = schema["function"]["name"]
        if name in tool_names and name not in known:
            definitions.append(schema)
    return definitions


def get_subagent_tool_definitions(
    *,
    toolsets: list[str] | None = None,
    mcp_servers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Resolve sub-agent tools from toolsets with delegate blocking and optional MCP subset."""
    ensure_tools_loaded()
    names: set[str] = set()
    for toolset_name in toolsets or ["evolux-code"]:
        names |= resolve_toolset(toolset_name)
    names = filter_subagent_tools(names)
    if mcp_servers:
        names |= {name for name in _mcp_tool_names() if name.startswith(tuple(f"mcp_{s}_" for s in mcp_servers))}
    names = apply_mcp_allowlist(names, mcp_servers if mcp_servers is not None else [])
    return registry.get_definitions(names)


def handle_function_call(name: str, arguments: dict[str, Any] | str, **kwargs: Any) -> str:
    ensure_tools_loaded()
    return registry.dispatch(name, arguments, **kwargs)


def filter_subagent_tools(tool_names: set[str]) -> set[str]:
    return {name for name in tool_names if name not in DELEGATE_BLOCKED_TOOLS}
