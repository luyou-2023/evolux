"""Hermes-compatible slash commands handled by the session monitor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent.turn_cancel import clear_turn_cancel, request_turn_cancel
from evolux_state import SessionDB

MONITOR_PREFIX = "📋 监控"

SLASH_ALIASES: dict[str, str] = {
    "reset": "new",
    "clear": "new",
    "commands": "help",
}


@dataclass
class SlashCommandContext:
    session_key: str
    assistant_id: str
    platform: str
    session_db: SessionDB
    on_progress: Callable[[str], None] | None = None


@dataclass
class SlashCommandOutcome:
    handled: bool
    reply: str | None = None
    rerun_message: str | None = None
    plain_reply: bool = True


def parse_slash_command(text: str) -> tuple[str, str] | None:
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None
    body = raw[1:].strip()
    if not body:
        return ("help", "")
    parts = body.split(None, 1)
    command = SLASH_ALIASES.get(parts[0].lower(), parts[0].lower())
    args = parts[1].strip() if len(parts) > 1 else ""
    return command, args


def try_handle_slash_command(text: str, *, ctx: SlashCommandContext) -> SlashCommandOutcome | None:
    parsed = parse_slash_command(text)
    if parsed is None:
        return None
    command, args = parsed
    handler = _HANDLERS.get(command)
    if handler is None:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 未知命令 `/{command}`，输入 /help 查看可用命令。",
        )
    return handler(ctx, args)


def _notify(ctx: SlashCommandContext, message: str) -> None:
    if ctx.on_progress:
        ctx.on_progress(message)


def _cmd_help(_ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    lines = [
        f"{MONITOR_PREFIX} · 可用命令（Hermes 兼容子集）：",
        "/help — 显示此帮助",
        "/new, /reset, /clear — 重置当前会话",
        "/stop — 中断正在运行的 Agent 轮次",
        "/status — 显示会话信息",
        "/history [n] — 显示最近消息（默认 6 条）",
        "/retry — 重试上一条用户消息",
        "/undo — 撤销上一轮对话",
    ]
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_new(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    ctx.session_db.reset_session(ctx.session_key, ctx.assistant_id, ctx.platform)
    clear_turn_cancel(ctx.session_key)
    message = f"{MONITOR_PREFIX} · 已开始新会话，历史记录已清空。"
    _notify(ctx, message)
    return SlashCommandOutcome(handled=True, reply=message)


def _cmd_stop(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    request_turn_cancel(ctx.session_key)
    message = f"{MONITOR_PREFIX} · 已发送停止信号，正在中断当前任务…"
    _notify(ctx, message)
    return SlashCommandOutcome(handled=True, reply=message)


def _cmd_status(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 尚无会话记录。",
        )
    count = ctx.session_db.count_messages(session_id)
    lines = [
        f"{MONITOR_PREFIX} · 会话状态",
        f"Session: {ctx.session_key}",
        f"Assistant: {ctx.assistant_id}",
        f"Platform: {ctx.platform}",
        f"Messages: {count}",
    ]
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_history(ctx: SlashCommandContext, args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 尚无历史消息。")
    limit = 6
    if args.strip().isdigit():
        limit = max(1, min(int(args.strip()), 20))
    messages = ctx.session_db.get_messages(session_id)[-limit:]
    if not messages:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 尚无历史消息。")
    lines = [f"{MONITOR_PREFIX} · 最近 {len(messages)} 条消息："]
    for item in messages:
        role = item["role"]
        content = str(item["content"] or "").replace("\n", " ")[:120]
        lines.append(f"[{role}] {content}")
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_retry(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 没有可重试的消息。")
    last_user = ctx.session_db.get_last_user_message(session_id)
    if not last_user:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 没有可重试的消息。")
    if not ctx.session_db.pop_last_exchange(session_id):
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 没有可重试的完整轮次。")
    _notify(ctx, f"{MONITOR_PREFIX} · 正在重试上一条消息…")
    return SlashCommandOutcome(handled=True, rerun_message=last_user, plain_reply=False)


def _cmd_undo(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id or not ctx.session_db.pop_last_exchange(session_id):
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 没有可撤销的对话。")
    message = f"{MONITOR_PREFIX} · 已撤销上一轮对话。"
    _notify(ctx, message)
    return SlashCommandOutcome(handled=True, reply=message)


_HANDLERS = {
    "help": _cmd_help,
    "new": _cmd_new,
    "stop": _cmd_stop,
    "status": _cmd_status,
    "history": _cmd_history,
    "retry": _cmd_retry,
    "undo": _cmd_undo,
}
