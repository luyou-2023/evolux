"""Render TurnTrace for terminal output."""

from __future__ import annotations

import sys

from agent.turn_trace import TurnTrace

_CATEGORY_LABEL = {
    "orchestrator": "主控",
    "subagent": "子Agent",
    "mcp": "MCP",
    "builtin": "工具",
}


def render_trace(trace: TurnTrace, *, stream=None) -> None:
    out = stream or sys.stderr
    if not _has_content(trace):
        return

    out.write("\n── Evolux 协调过程 ──\n")
    if trace.routing_skills:
        out.write(f"  路由 Skill: {', '.join(trace.routing_skills)}\n")
    if trace.routing_agents:
        out.write(f"  候选子 Agent: {', '.join(trace.routing_agents)}\n")

    for step in trace.steps:
        label = _CATEGORY_LABEL.get(step.category, step.category)
        mark = "✓" if step.status == "ok" else "✗"
        out.write(f"  {mark} [{label}] {step.title}\n")
        if step.detail:
            for line in step.detail.splitlines()[:3]:
                out.write(f"      {line[:100]}\n")
    out.write("────────────────────\n")


def _has_content(trace: TurnTrace) -> bool:
    return bool(trace.routing_skills or trace.routing_agents or trace.steps)
