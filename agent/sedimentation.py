"""Post-task memory and solution sedimentation for expert reuse."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.memory_manager import MemoryManager

ENTRY_DELIMITER = "\n§\n"

DOMAIN_TOOLSETS: dict[str, list[str]] = {
    "code": ["evolux-code"],
    "feishu": ["evolux-feishu"],
    "ui-test": ["evolux-ui-test"],
    "writing": ["evolux-code"],
    "research": ["evolux-code"],
    "general": ["evolux-code"],
}

UI_TEST_MCP_NAME_HINTS = ("midscene",)

# MCP server name substrings that indicate code/opencode capability in config.yaml
CODE_MCP_NAME_HINTS = ("opencode", "devtools", "code", "cdp")


def default_toolsets_for_domain(domain: str) -> list[str]:
    return list(DOMAIN_TOOLSETS.get((domain or "general").lower(), ["evolux-code"]))


def default_mcp_servers_for_domain(
    domain: str,
    mcp_servers: dict[str, Any] | None = None,
) -> list[str]:
    """Pick enabled MCP servers from config for a domain (code → opencode/devtools-like names)."""
    if not mcp_servers:
        return []
    domain_lower = (domain or "").lower()
    if domain_lower == "ui-test":
        return []
    if domain_lower != "code":
        return []
    selected: list[str] = []
    for name, cfg in mcp_servers.items():
        if not isinstance(cfg, dict) or cfg.get("enabled") is False:
            continue
        name_lower = str(name).lower()
        if any(hint in name_lower for hint in CODE_MCP_NAME_HINTS):
            selected.append(str(name))
    return selected


def _code_execution_instructions(mcp_servers: list[str]) -> str:
    if not mcp_servers:
        return (
            "代码任务：若 config 中无 MCP，可用 terminal/write_file；"
            "摘要须如实列出实际工具名，勿声称使用了 opencode/MCP。"
        )
    mcp_line = ", ".join(mcp_servers)
    return (
        f"代码任务必须通过 MCP 工具执行（绑定服务: {mcp_line}，工具名前缀 mcp_{{server}}_*）。\n"
        "禁止用 write_file/terminal 绕过 MCP 写代码，除非 MCP 调用失败且已在摘要中说明。\n"
        "摘要须列出实际调用的 MCP 工具名；未调用 MCP 时不得声称使用了 opencode。"
    )


def build_dispatch_context_slice(
    *,
    toolsets: list[str],
    mcp_servers: list[str],
    domain: str,
    context_slice: str = "",
) -> str:
    """Inject capability constraints so sub-agents do not bypass bound MCP."""
    parts: list[str] = []
    if context_slice.strip():
        parts.append(context_slice.strip())
    cap = f"绑定 toolsets: {', '.join(toolsets) or 'evolux-code'}"
    cap += f"\n绑定 MCP: {', '.join(mcp_servers) if mcp_servers else '无'}"
    if (domain or "").lower() == "code":
        cap += f"\n\n{_code_execution_instructions(mcp_servers)}"
    elif (domain or "").lower() == "ui-test":
        cap += (
            "\n\nUI 测试必须使用 midscene_luke_run 或 midscene_luke_run_playwright_test；"
            "禁止 terminal 模拟浏览器操作。"
        )
    parts.append(cap)
    return "\n\n".join(parts)


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
    extra = ""
    if (domain or "").lower() == "code":
        extra = f"\n\n{_code_execution_instructions(mcp_servers)}"
    elif (domain or "").lower() == "ui-test":
        extra = (
            "\n\nUI 测试任务必须使用 midscene_luke_run 或 midscene_luke_run_playwright_test，"
            "禁止用 terminal/curl 模拟点击。摘要须含步骤结果与断言结论。"
        )
    return (
        f"你是 {name}，{domain} 领域专家。\n"
        f"{description.strip() or '专注执行主控委派的具体任务。'}\n\n"
        "职责：使用绑定 skills 与工具完成委派任务，返回结构化摘要（结论、关键步骤、产出路径、实际使用的工具名）。\n"
        f"绑定 skills: {skill_line}\n"
        f"绑定 toolsets: {toolset_line}\n"
        f"绑定 MCP: {mcp_line}"
        f"{extra}"
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
