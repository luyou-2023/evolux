"""Built-in session monitor sub-agent — observes orchestration and pushes progress."""

from __future__ import annotations

import json
from typing import Any, Callable

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.turn_trace import categorize_tool, tool_title
from gateway.activity import emit_activity

SESSION_MONITOR_AGENT_ID = "_session-monitor"
INTERNAL_AGENT_PREFIX = "_"


def is_internal_agent(agent_id: str) -> bool:
    return str(agent_id).startswith(INTERNAL_AGENT_PREFIX)


def default_monitor_agent(assistant_id: str) -> AgentDefinition:
    return AgentDefinition(
        agent_id=SESSION_MONITOR_AGENT_ID,
        assistant_id=assistant_id,
        name="Session Monitor",
        domain="orchestration",
        description="内置监控子 Agent：观察主 Agent 协调子 Agent 的执行进度，并向用户推送状态更新。",
        system_prompt_template=(
            "你是 Evolux 内置会话监控 Agent。你不直接执行任务，只观察主控 Agent "
            "如何委派、创建和协调子 Agent，并将进度以简洁中文推送给用户。"
        ),
        toolsets=[],
        skills=[],
        stats={"internal": True},
    )


def ensure_session_monitor_agent(registry: AgentRegistry, assistant_id: str) -> AgentDefinition:
    existing = registry.get(SESSION_MONITOR_AGENT_ID, include_retired=True)
    if existing is not None:
        if existing.retired:
            existing.retired = False
            registry.register(existing)
        return existing
    agent = default_monitor_agent(assistant_id)
    registry.register(agent)
    return agent


def format_progress_start(name: str, arguments: dict[str, Any], *, nested_agent_id: str = "") -> str | None:
    prefix = f"📋 监控 · {nested_agent_id} · " if nested_agent_id else "📋 监控 · "
    if name == "dispatch_subagent":
        agent_id = str(arguments.get("agent_id") or "?")
        task = str(arguments.get("task") or "")[:100]
        return f"{prefix}委派 **{agent_id}** 执行：{task or '…'}"
    if name == "create_subagent":
        return f"{prefix}创建子 Agent **{arguments.get('agent_id', '?')}**"
    if name == "search_subagents":
        return f"{prefix}检索匹配的子 Agent…"
    if name == "identify_skills":
        return f"{prefix}识别相关 Skill…"
    if name == "clarify":
        question = str(arguments.get("question") or "")[:80]
        return f"{prefix}等待用户确认：{question or '…'}"
    if nested_agent_id:
        return f"{prefix}{tool_title(name, arguments)}"
    if categorize_tool(name) == "orchestrator":
        return f"{prefix}{tool_title(name, arguments)}"
    return None


def format_progress_end(name: str, arguments: dict[str, Any], result: str, *, nested_agent_id: str = "") -> str | None:
    prefix = f"📋 监控 · {nested_agent_id} · " if nested_agent_id else "📋 监控 · "
    if name == "dispatch_subagent":
        agent_id = str(arguments.get("agent_id") or "?")
        status = _result_status(result)
        icon = "✅" if status == "ok" else "⚠️"
        summary = _result_summary(result)
        return f"{icon} {prefix}**{agent_id}** {status_label(status)}{summary}"
    if name == "create_subagent":
        agent_id = str(arguments.get("agent_id") or "?")
        if _looks_like_error(result):
            return f"⚠️ {prefix}创建 **{agent_id}** 失败"
        return f"✅ {prefix}已注册子 Agent **{agent_id}**"
    if nested_agent_id and categorize_tool(name) in {"mcp", "builtin"}:
        icon = "✅" if not _looks_like_error(result) else "⚠️"
        return f"{icon} {prefix}{tool_title(name, arguments)}"
    return None


def turn_start_message(user_message: str) -> str:
    preview = (user_message or "").strip()[:60]
    if preview:
        return f"📋 监控 · 开始处理：{preview}"
    return "📋 监控 · 开始处理请求…"


def turn_end_message(*, subagent_count: int) -> str | None:
    if subagent_count <= 0:
        return None
    return f"📋 监控 · 本轮协调了 {subagent_count} 个子 Agent，正在汇总回复…"


def _result_status(result: str) -> str:
    if _looks_like_error(result):
        return "error"
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return "ok"
    if payload.get("error"):
        return "error"
    if payload.get("exhausted"):
        return "exhausted"
    return "ok"


def _result_summary(result: str) -> str:
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return ""
    content = str(payload.get("content") or "").strip()
    if not content:
        return ""
    return f" — {content[:80]}"


def status_label(status: str) -> str:
    if status == "error":
        return "执行失败"
    if status == "exhausted":
        return "迭代耗尽"
    return "已完成"


def _looks_like_error(result: str) -> bool:
    text = (result or "").strip().lower()
    return text.startswith('{"error"') or '"error":' in text[:80]


class SessionMonitorHook:
    """Observe tool execution and push user-visible orchestration progress."""

    def __init__(
        self,
        *,
        session_key: str,
        assistant_id: str,
        platform: str,
        on_progress: Callable[[str], None] | None = None,
        nested_agent_id: str = "",
    ) -> None:
        self.session_key = session_key
        self.assistant_id = assistant_id
        self.platform = platform
        self._on_progress = on_progress
        self._nested_agent_id = nested_agent_id
        self.subagent_dispatches = 0

    def push(self, message: str) -> None:
        emit_activity(
            "progress_update",
            session_key=self.session_key,
            assistant_id=self.assistant_id,
            platform=self.platform,
            tool=SESSION_MONITOR_AGENT_ID,
            detail=message,
        )
        if self._on_progress:
            self._on_progress(message)

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        message = format_progress_start(name, arguments, nested_agent_id=self._nested_agent_id)
        if message:
            self.push(message)

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        if name == "dispatch_subagent" and not self._nested_agent_id:
            self.subagent_dispatches += 1
        message = format_progress_end(name, arguments, result, nested_agent_id=self._nested_agent_id)
        if message:
            self.push(message)
