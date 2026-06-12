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
    "terminal": "execute",
    "web_search": "fetch",
    "web_extract": "fetch",
    "identify_skills": "other",
    "search_subagents": "search",
    "list_subagents": "read",
    "create_subagent": "execute",
    "dispatch_subagent": "execute",
    "retire_subagent": "execute",
    "clarify": "other",
    "feishu_message": "other",
    "feishu_doc_read": "read",
    "feishu_doc_create": "edit",
}


def get_tool_kind(tool_name: str) -> ToolKind:
    if tool_name.startswith("mcp_"):
        return "other"
    return TOOL_KIND_MAP.get(tool_name, "other")


def build_tool_title(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "terminal":
        cmd = str(args.get("command", ""))
        return f"terminal: {cmd[:80]}"
    if tool_name == "web_search":
        return f"web search: {args.get('query', '?')}"
    if tool_name == "read_file":
        return f"read: {args.get('path', '?')}"
    if tool_name == "feishu_doc_read":
        return f"feishu doc: {args.get('document_id', '?')}"
    if tool_name == "feishu_message":
        return f"feishu message → {args.get('chat_id', '?')}"
    return tool_name
