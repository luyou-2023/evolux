"""Post-task memory and solution sedimentation for expert reuse."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.memory_manager import MemoryManager

ENTRY_DELIMITER = "\n§\n"

DOMAIN_TOOLSETS: dict[str, list[str]] = {
    "code": ["evolux-code"],
    "feishu": ["evolux-feishu"],
    "writing": ["evolux-code"],
    "research": ["evolux-code"],
    "general": ["evolux-code"],
}


def default_toolsets_for_domain(domain: str) -> list[str]:
    return list(DOMAIN_TOOLSETS.get((domain or "general").lower(), ["evolux-code"]))


def build_default_system_prompt(
    *,
    name: str,
    domain: str,
    description: str,
    skills: list[str],
    toolsets: list[str],
    mcp_servers: list[str],
) -> str:
    skill_line = ", ".join(skills) if skills else "（由路由动态绑定）"
    toolset_line = ", ".join(toolsets) if toolsets else "evolux-code"
    mcp_line = ", ".join(mcp_servers) if mcp_servers else "无"
    return (
        f"你是 {name}，{domain} 领域专家。\n"
        f"{description.strip() or '专注执行主控委派的具体任务。'}\n\n"
        "职责：使用绑定 skills 与工具完成委派任务，返回结构化摘要（结论、关键步骤、产出路径）。\n"
        f"绑定 skills: {skill_line}\n"
        f"绑定 toolsets: {toolset_line}\n"
        f"绑定 MCP: {mcp_line}"
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sediment_agent_task(
    memory: MemoryManager,
    *,
    agent_id: str,
    task: str,
    summary: str,
    skills: list[str],
) -> None:
    if not summary or not summary.strip():
        return
    skill_text = ", ".join(skills) if skills else "-"
    entry = (
        f"[{_timestamp()}] 任务: {task.strip()[:500]}\n"
        f"skills: [{skill_text}]\n"
        f"结论: {summary.strip()[:2000]}"
    )
    memory.append_agent_memory(agent_id, entry)


def sediment_turn_solution(
    memory: MemoryManager,
    *,
    user_message: str,
    final_reply: str,
    dispatches: list[dict[str, Any]],
) -> None:
    if not dispatches:
        return
    agent_ids = ", ".join(item["agent_id"] for item in dispatches)
    skills_used: set[str] = set()
    for item in dispatches:
        skills_used.update(item.get("skills") or [])
    skill_text = ", ".join(sorted(skills_used)) if skills_used else "-"
    dispatch_lines = []
    for item in dispatches:
        status = "失败" if item.get("exhausted") else "成功"
        dispatch_lines.append(
            f"- {item['agent_id']} ({status}): {str(item.get('summary') or '')[:300]}"
        )
    entry = (
        f"[{_timestamp()}]\n"
        f"用户需求: {user_message.strip()[:500]}\n"
        f"委派专家: {agent_ids}\n"
        f"使用 skills: [{skill_text}]\n"
        f"执行摘要:\n" + "\n".join(dispatch_lines) + "\n"
        f"最终答复: {(final_reply or '').strip()[:800]}"
    )
    memory.append_solution(entry)
