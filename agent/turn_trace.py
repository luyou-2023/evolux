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
    if name == "create_subagent":
        return f"创建专家 · {arguments.get('agent_id', '?')}"
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


def _split_subagent_detail(detail: str) -> tuple[str, str]:
    if " → " in detail:
        task, outcome = detail.split(" → ", 1)
        return task.strip(), outcome.strip()
    return (detail or "").strip(), ""


def format_coordination_summary(trace: TurnTrace) -> list[str]:
    """Summarize which expert agents ran and what they produced (no raw tool dumps)."""
    lines: list[str] = []

    if trace.routing_skills:
        shown = trace.routing_skills[:6]
        suffix = f" 等{len(trace.routing_skills)}个" if len(trace.routing_skills) > len(shown) else ""
        lines.append(f"识别 Skill: {', '.join(shown)}{suffix}")

    expert_steps = [step for step in trace.steps if step.category == "subagent"]
    if expert_steps:
        lines.append(f"本轮协调 {len(expert_steps)} 位专家：")
        for step in expert_steps:
            task, outcome = _split_subagent_detail(step.detail)
            icon = "✅" if step.status == "ok" else "⚠️"
            lines.append(f"{icon} {step.name}")
            if task:
                lines.append(f"   · 任务: {task[:120]}")
            if outcome:
                lines.append(f"   · 产出: {outcome[:160]}")
        return lines

    created: list[str] = []
    dispatched: list[str] = []
    for step in trace.steps:
        if step.category != "orchestrator":
            continue
        if step.name == "create_subagent":
            agent_id = step.title.replace("创建专家 · ", "").strip()
            if agent_id:
                created.append(agent_id)
        elif step.name == "dispatch_subagent":
            agent_id = step.title.replace("委派 · ", "").strip()
            if agent_id:
                dispatched.append(agent_id)

    if created:
        lines.append(f"新建专家: {', '.join(created)}")
    if dispatched:
        lines.append(f"已委派: {', '.join(dispatched)}")
    elif trace.routing_agents:
        shown = trace.routing_agents[:5]
        suffix = f" 等{len(trace.routing_agents)}个" if len(trace.routing_agents) > len(shown) else ""
        lines.append(f"路由候选: {', '.join(shown)}{suffix}")

    return lines
