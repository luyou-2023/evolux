"""Routing-aware tool selection to reduce LLM tool schema size."""

from __future__ import annotations

from typing import Any

from agent.routing import RoutingContext

ORCHESTRATOR_ALWAYS = frozenset(
    {
        "identify_skills",
        "search_subagents",
        "list_subagents",
        "create_subagent",
        "dispatch_subagent",
        "retire_subagent",
        "clarify",
        "skills_list",
        "skill_view",
        "memory",
        "session_search",
    }
)

PLATFORM_BASE: dict[str, frozenset[str]] = {
    "cli": frozenset({"read_file", "write_file", "todo", "terminal", "web_search", "web_extract"}),
    "feishu": frozenset({"feishu_message", "feishu_doc_read"}),
    "acp": frozenset({"read_file", "write_file", "terminal", "web_search", "todo"}),
    "cron": frozenset(),
}

SKILL_TOOL_HINTS: dict[str, frozenset[str]] = {
    "feishu-doc": frozenset(
        {"feishu_message", "feishu_doc_read", "feishu_doc_create", "feishu_doc_append"}
    ),
    "git": frozenset({"terminal", "read_file", "write_file"}),
    "plan": frozenset({"todo"}),
    "native-mcp": frozenset(),
}


def select_tools_for_turn(
    definitions: list[dict[str, Any]],
    routing: RoutingContext,
    *,
    platform: str = "cli",
    max_tools: int = 40,
    include_mcp: bool = True,
) -> list[dict[str, Any]]:
    """Trim tool definitions using routing signals while keeping orchestrator essentials."""
    if not definitions:
        return []

    by_name = {
        item["function"]["name"]: item
        for item in definitions
        if item.get("function") and item["function"].get("name")
    }
    selected: set[str] = set(ORCHESTRATOR_ALWAYS)
    selected |= PLATFORM_BASE.get(platform, PLATFORM_BASE["cli"])

    for candidate in routing.skill_candidates[:5]:
        selected |= SKILL_TOOL_HINTS.get(candidate.skill_name, set())
    for skill_name in routing.suggested_skills:
        selected |= SKILL_TOOL_HINTS.get(skill_name, set())

    selected = {name for name in selected if name in by_name}

    if include_mcp:
        mcp_names = [name for name in by_name if name.startswith("mcp_")]
        for name in mcp_names:
            if len(selected) >= max_tools:
                break
            selected.add(name)

    priority = list(ORCHESTRATOR_ALWAYS) + sorted(selected - ORCHESTRATOR_ALWAYS)
    ordered = [by_name[name] for name in priority if name in selected]
    if len(ordered) > max_tools:
        ordered = ordered[:max_tools]
    return ordered
