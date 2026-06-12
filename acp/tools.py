"""ACP tool mapping aligned with Hermes acp_adapter.tools."""

from __future__ import annotations

from typing import Any

ToolKind = str

TOOL_KIND_MAP: dict[str, ToolKind] = {
    "read_file": "read",
    "write_file": "edit",
    "skills_list": "read",
    "skill_view": "read",
    "memory": "other",
    "session_search": "search",
    "todo": "other",
    "identify_skills": "other",
    "search_subagents": "search",
    "list_subagents": "read",
    "create_subagent": "execute",
    "dispatch_subagent": "execute",
    "retire_subagent": "execute",
}


def get_tool_kind(tool_name: str) -> ToolKind:
    if tool_name.startswith("mcp_"):
        return "other"
    return TOOL_KIND_MAP.get(tool_name, "other")


def build_tool_title(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "read_file":
        return f"read: {args.get('path', '?')}"
    if tool_name == "write_file":
        return f"write: {args.get('path', '?')}"
    if tool_name == "skill_view":
        return f"skill view: {args.get('name', '?')}"
    if tool_name == "skills_list":
        return "skills list"
    if tool_name == "session_search":
        query = str(args.get("query") or "").strip()
        return f"session search: {query}" if query else "recent sessions"
    if tool_name == "dispatch_subagent":
        return f"dispatch: {args.get('agent_id', '?')}"
    return tool_name
