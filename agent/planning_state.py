"""Per-turn planning context for orchestrator coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.routing import RoutingContext


def format_plan_block(goal: str, steps: list[dict[str, Any]]) -> str:
    lines = ["## 当前执行计划（plan_task）", ""]
    if goal:
        lines.append(f"**目标:** {goal}")
        lines.append("")
    lines.append("**步骤:**")
    if not steps:
        lines.append("- （无）")
    else:
        for idx, step in enumerate(steps, start=1):
            action = str(step.get("action") or step.get("content") or "").strip()
            agent_id = str(step.get("agent_id") or "").strip()
            skills = step.get("skills") or []
            suffix = f" → `{agent_id}`" if agent_id else ""
            if skills:
                suffix += f" skills={skills}"
            lines.append(f"{idx}. {action}{suffix}")
    return "\n".join(lines)


@dataclass
class TurnPlanningState:
    session_key: str = ""
    routing: RoutingContext | None = None
    user_message: str = ""
    dispatch_count: int = 0
    dispatches: list[dict[str, Any]] = field(default_factory=list)
    plan_goal: str = ""
    plan_steps: list[dict[str, Any]] = field(default_factory=list)

    def reset(self, *, user_message: str = "", session_key: str = "") -> None:
        self.session_key = session_key
        self.routing = None
        self.user_message = user_message
        self.dispatch_count = 0
        self.dispatches.clear()
        self.plan_goal = ""
        self.plan_steps.clear()

    def record_dispatch(
        self,
        *,
        agent_id: str,
        task: str,
        skills: list[str],
        summary: str,
        exhausted: bool,
    ) -> None:
        self.dispatch_count += 1
        self.dispatches.append(
            {
                "agent_id": agent_id,
                "task": task,
                "skills": skills,
                "summary": summary,
                "exhausted": exhausted,
            }
        )
