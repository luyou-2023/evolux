"""Toolset definitions aligned with Hermes presets (Evolux naming)."""

from __future__ import annotations

from typing import Any

# Hermes core operator tools adapted for Evolux orchestrator runtime.
_EVOLUX_CORE_TOOLS = [
    "skills_list",
    "skill_view",
    "memory",
    "session_search",
    "read_file",
    "write_file",
    "todo",
    "identify_skills",
    "search_subagents",
    "list_subagents",
    "create_subagent",
    "dispatch_subagent",
    "retire_subagent",
]

TOOLSETS: dict[str, dict[str, Any]] = {
    "skills": {
        "description": "Skill discovery and progressive disclosure (Hermes-compatible)",
        "tools": ["skills_list", "skill_view"],
        "includes": [],
    },
    "memory": {
        "description": "Persistent MEMORY.md / USER.md curation",
        "tools": ["memory"],
        "includes": [],
    },
    "session_search": {
        "description": "Browse and search orchestrator sessions",
        "tools": ["session_search"],
        "includes": [],
    },
    "file": {
        "description": "Read/write files under EVOLUX_HOME",
        "tools": ["read_file", "write_file"],
        "includes": [],
    },
    "todo": {
        "description": "Lightweight task planning list",
        "tools": ["todo"],
        "includes": [],
    },
    "evolux-orchestrator": {
        "description": "Evolux orchestrator coordination tools",
        "tools": [
            "identify_skills",
            "search_subagents",
            "list_subagents",
            "create_subagent",
            "dispatch_subagent",
            "retire_subagent",
            "skills_list",
            "skill_view",
            "memory",
            "session_search",
        ],
        "includes": [],
    },
    "evolux-code": {
        "description": "CLI coding assistant preset",
        "tools": [],
        "includes": ["file", "skills", "memory", "session_search", "todo"],
    },
    "evolux-feishu": {
        "description": "Feishu platform preset (doc tools future)",
        "tools": [],
        "includes": ["evolux-orchestrator"],
    },
    "evolux-acp": {
        "description": "Editor integration preset (Hermes hermes-acp aligned)",
        "tools": [
            "read_file",
            "write_file",
            "skills_list",
            "skill_view",
            "memory",
            "session_search",
            "todo",
            "identify_skills",
            "search_subagents",
            "list_subagents",
            "create_subagent",
            "dispatch_subagent",
            "retire_subagent",
        ],
        "includes": [],
    },
    "hermes-acp": {
        "description": "Alias of evolux-acp for Hermes compatibility",
        "tools": [],
        "includes": ["evolux-acp"],
    },
}

PLATFORM_TOOLSETS: dict[str, list[str]] = {
    "cli": ["evolux-orchestrator", "evolux-code"],
    "feishu": ["evolux-orchestrator", "evolux-feishu"],
    "cron": ["evolux-orchestrator"],
    "acp": ["evolux-acp"],
}

DELEGATE_BLOCKED_TOOLS = frozenset(
    {
        "dispatch_subagent",
        "create_subagent",
        "retire_subagent",
        "identify_skills",
        "search_subagents",
        "list_subagents",
        "clarify",
    }
)


def resolve_toolset(name: str, *, _stack: set[str] | None = None) -> set[str]:
    stack = _stack or set()
    if name in stack:
        return set()
    stack.add(name)
    cfg = TOOLSETS.get(name)
    if not cfg:
        return {name} if name in _all_registered_tool_names() else set()
    tools = set(cfg.get("tools") or [])
    for included in cfg.get("includes") or []:
        tools |= resolve_toolset(str(included), _stack=stack)
    return tools


def resolve_platform_toolsets(platform: str) -> set[str]:
    names = set(_EVOLUX_CORE_TOOLS)
    for toolset_name in PLATFORM_TOOLSETS.get(platform, ["evolux-orchestrator"]):
        names |= resolve_toolset(toolset_name)
    return names


def _all_registered_tool_names() -> set[str]:
    names: set[str] = set()
    for cfg in TOOLSETS.values():
        names.update(cfg.get("tools") or [])
    return names
