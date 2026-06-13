"""Built-in session monitor sub-agent — observes orchestration and pushes progress."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.turn_trace import categorize_tool, tool_title
from gateway.activity import emit_activity

SESSION_MONITOR_AGENT_ID = "_session-monitor"
INTERNAL_AGENT_PREFIX = "_"

HIGH_PRIORITY_TOOLS = frozenset(
    {
        "dispatch_subagent",
        "create_subagent",
        "clarify",
    }
)


def is_internal_agent(agent_id: str) -> bool:
    return str(agent_id).startswith(INTERNAL_AGENT_PREFIX)


def default_monitor_agent(assistant_id: str) -> AgentDefinition:
    return AgentDefinition(
        agent_id=SESSION_MONITOR_AGENT_ID,
        assistant_id=assistant_id,
        name="Session Monitor",
        domain="orchestration",
        description="内置监控子 Agent：观察主 Agent 协调进度、向用户推送状态，并执行 /help /stop /new 等 Hermes 会话命令。",
        system_prompt_template=(
            "你是 Evolux 内置会话监控 Agent。你不直接执行任务，负责："
            "1) 观察主控 Agent 如何委派和协调子 Agent；"
            "2) 向用户推送协调进度；"
            "3) 处理 /help、/new、/stop、/status 等 slash 命令。"
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
    if nested_agent_id:
        return None
    prefix = "📋 监控 · "
    if name == "dispatch_subagent":
        agent_id = str(arguments.get("agent_id") or "?")
        task = str(arguments.get("task") or "")[:80]
        return f"{prefix}委派 **{agent_id}** · {task or '…'}"
    if name == "create_subagent":
        return f"{prefix}创建子 Agent **{arguments.get('agent_id', '?')}**"
    if name == "search_subagents":
        return f"{prefix}检索子 Agent…"
    if name == "identify_skills":
        return f"{prefix}识别 Skill…"
    if name == "clarify":
        question = str(arguments.get("question") or "")[:80]
        return f"{prefix}等待确认：{question or '…'}"
    if categorize_tool(name) == "orchestrator":
        return f"{prefix}{tool_title(name, arguments)}"
    return None


def format_progress_end(name: str, arguments: dict[str, Any], result: str, *, nested_agent_id: str = "") -> str | None:
    if nested_agent_id:
        return None
    prefix = "📋 监控 · "
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
    return None


def format_turn_summary(
    *,
    active: list[str],
    completed: int,
    total: int,
    elapsed_seconds: float,
) -> str | None:
    if total <= 0 and not active:
        return None
    done = completed
    total = max(total, done + len(active))
    elapsed = int(elapsed_seconds)
    line = f"📋 进度 {done}/{total} · 已耗时 {elapsed}s"
    if active:
        line = f"{line} · 进行中：{', '.join(active[:3])}"
    return line


def turn_start_message(user_message: str) -> str:
    preview = (user_message or "").strip()[:60]
    if preview:
        return f"📋 监控 · 开始：{preview}"
    return "📋 监控 · 开始处理…"


def turn_end_message(*, subagent_count: int) -> str | None:
    if subagent_count <= 0:
        return None
    return f"📋 监控 · 已协调 {subagent_count} 个子 Agent，正在汇总回复…"


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
        return "失败"
    if status == "exhausted":
        return "迭代耗尽"
    return "完成"


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
        min_push_interval_seconds: float = 12.0,
        summary_interval_seconds: float = 45.0,
        push_nested_tools: bool = False,
    ) -> None:
        self.session_key = session_key
        self.assistant_id = assistant_id
        self.platform = platform
        self._on_progress = on_progress
        self._nested_agent_id = nested_agent_id
        self._min_push_interval = max(0.0, float(min_push_interval_seconds))
        self._summary_interval = max(0.0, float(summary_interval_seconds))
        self._push_nested_tools = push_nested_tools
        self.subagent_dispatches = 0
        self._turn_started_at = time.monotonic()
        self._last_push_at = 0.0
        self._last_summary_at = 0.0
        self._active_subagents: list[str] = []
        self._completed_subagents = 0
        self._planned_subagents = 0

    def push(self, message: str, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._min_push_interval > 0
            and self._last_push_at
            and now - self._last_push_at < self._min_push_interval
        ):
            return
        self._last_push_at = now
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

    def maybe_push_summary(self, *, force: bool = False) -> None:
        if self._nested_agent_id:
            return
        now = time.monotonic()
        if not force and self._summary_interval > 0:
            if self._last_summary_at and now - self._last_summary_at < self._summary_interval:
                return
        message = format_turn_summary(
            active=list(self._active_subagents),
            completed=self._completed_subagents,
            total=self._planned_subagents,
            elapsed_seconds=now - self._turn_started_at,
        )
        if not message:
            return
        self._last_summary_at = now
        self.push(message, force=True)

    def on_tool_start(self, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        if self._nested_agent_id and not self._push_nested_tools:
            return
        if name == "dispatch_subagent" and not self._nested_agent_id:
            agent_id = str(arguments.get("agent_id") or "?")
            if agent_id not in self._active_subagents:
                self._active_subagents.append(agent_id)
            self._planned_subagents = max(self._planned_subagents, len(self._active_subagents) + self._completed_subagents)
        message = format_progress_start(name, arguments, nested_agent_id=self._nested_agent_id)
        if message:
            self.push(message, force=name in HIGH_PRIORITY_TOOLS)

    def on_tool_end(self, tool_call_id: str, name: str, arguments: dict[str, Any], result: str) -> None:
        if self._nested_agent_id and not self._push_nested_tools:
            return
        if name == "dispatch_subagent" and not self._nested_agent_id:
            self.subagent_dispatches += 1
            agent_id = str(arguments.get("agent_id") or "?")
            if agent_id in self._active_subagents:
                self._active_subagents.remove(agent_id)
            self._completed_subagents += 1
        message = format_progress_end(name, arguments, result, nested_agent_id=self._nested_agent_id)
        if message:
            self.push(message, force=True)
            self.maybe_push_summary(force=True)
        elif name == "dispatch_subagent" and not self._nested_agent_id:
            self.maybe_push_summary(force=False)
