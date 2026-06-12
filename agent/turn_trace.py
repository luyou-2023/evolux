"""Structured turn trace for CLI and Feishu user-visible orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ORCHESTRATOR_TOOLS = frozenset(
    {
        "identify_skills",
        "search_subagents",
        "list_subagents",
        "create_subagent",
        "dispatch_subagent",
        "retire_subagent",
        "clarify",
    }
)


@dataclass
class TraceStep:
    kind: str
    name: str
    title: str
    detail: str = ""
    category: str = "tool"
    status: str = "ok"
    agent_id: str = ""


@dataclass
class TurnTrace:
    user_message: str = ""
    routing_skills: list[str] = field(default_factory=list)
    routing_agents: list[str] = field(default_factory=list)
    steps: list[TraceStep] = field(default_factory=list)

    def set_routing(self, *, skills: list[str], agents: list[str]) -> None:
        self.routing_skills = skills
        self.routing_agents = agents

    def add_subagent(self, *, agent_id: str, task: str, summary: str, status: str = "ok") -> None:
        self.steps.append(
            TraceStep(
                kind="subagent",
                name=agent_id,
                title=f"子 Agent · {agent_id}",
                detail=f"{task[:120]} → {summary[:180]}",
                category="subagent",
                status=status,
            )
        )

    def add_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        result: str,
        agent_id: str = "",
    ) -> None:
        category = categorize_tool(name)
        title = tool_title(name, arguments)
        if agent_id:
            title = f"  └ {agent_id} · {title}"
        status = "error" if _looks_like_error(result) else "ok"
        self.steps.append(
            TraceStep(
                kind="tool",
                name=name,
                title=title,
                detail=(result or "")[:240],
                category=category,
                status=status,
                agent_id=agent_id,
            )
        )


def categorize_tool(name: str) -> str:
    if name.startswith("mcp_"):
        return "mcp"
    if name in ORCHESTRATOR_TOOLS:
        return "orchestrator"
    return "builtin"


def tool_title(name: str, arguments: dict[str, Any]) -> str:
    if name == "dispatch_subagent":
        return f"委派 · {arguments.get('agent_id', '?')}"
    if name == "terminal":
        cmd = str(arguments.get("command", ""))
        return f"终端 · {cmd[:60]}"
    if name == "read_file":
        return f"读取 · {arguments.get('path', '?')}"
    if name == "write_file":
        return f"写入 · {arguments.get('path', '?')}"
    if name.startswith("mcp_"):
        parts = name.split("_", 2)
        server = parts[1] if len(parts) > 2 else "mcp"
        tool = parts[2] if len(parts) > 2 else name
        return f"MCP · {server}/{tool}"
    if name == "clarify":
        return "澄清 · 向用户提问"
    return name.replace("_", " ")


def _looks_like_error(result: str) -> bool:
    text = (result or "").strip().lower()
    return text.startswith('{"error"') or '"error":' in text[:80]
