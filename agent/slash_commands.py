"""Hermes-compatible slash commands handled by the session monitor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.context_compressor import CompressionConfig, compress_messages
from agent.settings import Settings
from agent.turn_cancel import clear_turn_cancel, request_turn_cancel
from evolux_state import SessionDB

MONITOR_PREFIX = "📋 监控"

SLASH_ALIASES: dict[str, str] = {
    "reset": "new",
    "clear": "new",
}


@dataclass
class SlashCommandContext:
    session_key: str
    assistant_id: str
    platform: str
    session_db: SessionDB
    on_progress: Callable[[str], None] | None = None
    settings: Settings | None = None
    home: Path | None = None


@dataclass
class SlashCommandOutcome:
    handled: bool
    reply: str | None = None
    rerun_message: str | None = None
    plain_reply: bool = True
    interactive_card: dict[str, Any] | None = None
    switch_session_key: str | None = None


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


def _compression_config(ctx: SlashCommandContext) -> CompressionConfig:
    if ctx.settings is not None:
        return CompressionConfig(keep_recent_turns=ctx.settings.compression.keep_recent_turns)
    return CompressionConfig()


def _tool_names(platform: str) -> list[str]:
    from agent.tooling import get_agent_tool_definitions

    names: list[str] = []
    for item in get_agent_tool_definitions(platform=platform):
        fn = item.get("function") if isinstance(item, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            names.append(str(fn["name"]))
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return sorted(set(names))


def _cmd_help(_ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    lines = [
        f"{MONITOR_PREFIX} · 可用命令（Hermes 兼容子集）：",
        "/help — 显示此帮助",
        "/commands — 命令参考（飞书发送交互卡片）",
        "/new, /reset, /clear — 重置当前会话",
        "/title [名称] — 查看或设置会话标题",
        "/resume [标题] — 按标题恢复会话（CLI 可切换）",
        "/stop — 中断正在运行的 Agent 轮次",
        "/status — 显示会话与模型信息",
        "/sessions — 列出最近会话",
        "/skills browse — 浏览已安装 Skills",
        "/history [n] — 显示最近消息（默认 6 条）",
        "/compress [focus] — 手动压缩会话上下文",
        "/model — 显示当前 LLM 模型",
        "/tools — 列出当前可用工具",
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
    title = ctx.session_db.get_session_title(ctx.session_key)
    lines = [
        f"{MONITOR_PREFIX} · 会话状态",
        f"Session: {ctx.session_key}",
    ]
    if title:
        lines.append(f"Title: {title}")
    lines.extend(
        [
            f"Assistant: {ctx.assistant_id}",
            f"Platform: {ctx.platform}",
            f"Messages: {count}",
        ]
    )
    if ctx.settings is not None:
        lines.append(f"Model: {ctx.settings.llm.provider}/{ctx.settings.llm.model}")
        lines.append(f"Tools: {len(_tool_names(ctx.platform))}")
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_sessions(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    items = ctx.session_db.list_sessions(assistant_id=ctx.assistant_id, limit=10)
    if not items:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 尚无会话记录。")
    lines = [f"{MONITOR_PREFIX} · 最近 {len(items)} 个会话："]
    for item in items:
        key = str(item.get("session_key") or "")
        marker = " ← 当前" if key == ctx.session_key else ""
        count = item.get("message_count", 0)
        platform = item.get("platform", "")
        title = str(item.get("title") or "").strip()
        label = f"{title} · " if title else ""
        lines.append(f"• {label}{key} ({platform}, {count} msgs){marker}")
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


def _cmd_compress(ctx: SlashCommandContext, args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 尚无会话可压缩。")
    raw_messages = ctx.session_db.get_messages(session_id)
    if not raw_messages:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 尚无消息可压缩。")

    focus = args.strip()
    cfg = _compression_config(ctx)
    messages = [{"role": m["role"], "content": m["content"]} for m in raw_messages]

    def _summarize(old_messages: list[dict]) -> str:
        turn_estimate = max(1, len(old_messages) // 2)
        summary = f"Earlier conversation compressed ({turn_estimate} turns). Details omitted."
        if focus:
            summary += f"\nUser focus: {focus}"
        return summary

    result = compress_messages(messages, cfg, summarize=_summarize if focus else None)
    if not result.compressed:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 消息量未超过保留阈值（{cfg.keep_recent_turns} 轮），无需压缩。",
        )

    ctx.session_db.replace_messages(session_id, result.messages)
    before = len(raw_messages)
    after = len(result.messages)
    message = (
        f"{MONITOR_PREFIX} · 已压缩会话上下文：{before} 条 → {after} 条，"
        f"保留最近 {cfg.keep_recent_turns} 轮。"
    )
    if focus:
        message += f" 焦点：{focus}"
    _notify(ctx, message)
    return SlashCommandOutcome(handled=True, reply=message)


def _cmd_title(ctx: SlashCommandContext, args: str) -> SlashCommandOutcome:
    session_id = ctx.session_db.get_session_id_by_key(ctx.session_key)
    if not session_id:
        ctx.session_db.get_or_create_session(ctx.session_key, ctx.assistant_id, ctx.platform)
    title = args.strip()
    if not title:
        current = ctx.session_db.get_session_title(ctx.session_key)
        if not current:
            return SlashCommandOutcome(
                handled=True,
                reply=f"{MONITOR_PREFIX} · 当前会话尚未命名。用法：/title 我的项目",
            )
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 当前会话标题：**{current}**",
        )
    ctx.session_db.set_session_title(ctx.session_key, title[:120])
    message = f"{MONITOR_PREFIX} · 会话标题已设为：**{title[:120]}**"
    _notify(ctx, message)
    return SlashCommandOutcome(handled=True, reply=message)


def _cmd_skills(ctx: SlashCommandContext, args: str) -> SlashCommandOutcome:
    subcommand = (args.split()[0].lower() if args.strip() else "browse")
    if subcommand not in {"browse", "list"}:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 用法：/skills browse",
        )
    if ctx.home is None:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · Skills 目录不可用。",
        )
    from agent.skill_router import SkillRouter

    backend = ctx.settings.vector.backend if ctx.settings else "sqlite-vec"
    router = SkillRouter(ctx.home, backend=backend)
    skills = router.scan_skills()
    if not skills:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 尚未安装 Skills（~/.evolux/skills）。",
        )
    lines = [f"{MONITOR_PREFIX} · 已安装 Skills（{len(skills)}）："]
    for skill in skills[:20]:
        desc = (skill.description or "").replace("\n", " ")[:80]
        lines.append(f"• **{skill.skill_name}** — {desc or '无描述'}")
    if len(skills) > 20:
        lines.append(f"… 另有 {len(skills) - 20} 个未显示")
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_commands(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    if ctx.platform == "feishu":
        from gateway.platforms.feishu_format import build_feishu_commands_card

        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 命令参考见下方卡片。",
            interactive_card=build_feishu_commands_card(),
        )
    return _cmd_help(ctx, "")


def _format_session_line(item: dict[str, Any], *, current_key: str) -> str:
    title = str(item.get("title") or "").strip()
    key = str(item.get("session_key") or "")
    platform = str(item.get("platform") or "")
    count = item.get("message_count", 0)
    marker = " ← 当前" if key == current_key else ""
    return f"• **{title}** · {platform} · {count} msgs{marker}"


def _cmd_resume(ctx: SlashCommandContext, args: str) -> SlashCommandOutcome:
    query = args.strip()
    if not query:
        items = ctx.session_db.list_titled_sessions(
            ctx.assistant_id,
            platform="cli" if ctx.platform == "cli" else None,
            limit=8,
        )
        if not items:
            return SlashCommandOutcome(
                handled=True,
                reply=f"{MONITOR_PREFIX} · 没有已命名会话。先用 /title 命名，或 /resume 标题 恢复。",
            )
        lines = [f"{MONITOR_PREFIX} · 已命名会话（/resume 标题）："]
        lines.extend(_format_session_line(item, current_key=ctx.session_key) for item in items)
        return SlashCommandOutcome(handled=True, reply="\n".join(lines))

    matches = ctx.session_db.find_sessions_by_title(ctx.assistant_id, query, limit=8)
    if not matches:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 未找到标题匹配「{query}」的会话。",
        )

    if ctx.platform == "cli":
        cli_matches = [item for item in matches if item.get("platform") == "cli"]
        if not cli_matches:
            only = matches[0]
            return SlashCommandOutcome(
                handled=True,
                reply=(
                    f"{MONITOR_PREFIX} · 找到「{only.get('title')}」，但属于 "
                    f"{only.get('platform')} 平台，请在对应渠道继续。"
                ),
            )
        if len(cli_matches) > 1:
            lines = [f"{MONITOR_PREFIX} · 多个 CLI 会话匹配「{query}」："]
            lines.extend(_format_session_line(item, current_key=ctx.session_key) for item in cli_matches)
            lines.append("请使用更精确的标题。")
            return SlashCommandOutcome(handled=True, reply="\n".join(lines))
        target = cli_matches[0]
        target_key = str(target.get("session_key") or "")
        title = str(target.get("title") or query)
        if target_key == ctx.session_key:
            return SlashCommandOutcome(
                handled=True,
                reply=f"{MONITOR_PREFIX} · 已在会话「{title}」。",
            )
        count = target.get("message_count", 0)
        message = f"{MONITOR_PREFIX} · 已切换到会话「{title}」（{count} 条消息）。"
        _notify(ctx, message)
        return SlashCommandOutcome(
            handled=True,
            reply=message,
            switch_session_key=target_key,
        )

    same_platform = [item for item in matches if item.get("platform") == ctx.platform]
    if len(same_platform) == 1 and str(same_platform[0].get("session_key")) == ctx.session_key:
        title = str(same_platform[0].get("title") or query)
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 已在会话「{title}」。",
        )
    lines = [f"{MONITOR_PREFIX} · 匹配「{query}」的会话："]
    lines.extend(_format_session_line(item, current_key=ctx.session_key) for item in matches[:5])
    lines.append("当前渠道无法切换会话，请在对应平台继续。")
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_model(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    if ctx.settings is None:
        return SlashCommandOutcome(
            handled=True,
            reply=f"{MONITOR_PREFIX} · 模型信息不可用。",
        )
    llm = ctx.settings.llm
    lines = [
        f"{MONITOR_PREFIX} · 当前模型",
        f"Provider: {llm.provider}",
        f"Model: {llm.model}",
        f"Tool choice: {llm.tool_choice}",
    ]
    return SlashCommandOutcome(handled=True, reply="\n".join(lines))


def _cmd_tools(ctx: SlashCommandContext, _args: str) -> SlashCommandOutcome:
    names = _tool_names(ctx.platform)
    if not names:
        return SlashCommandOutcome(handled=True, reply=f"{MONITOR_PREFIX} · 当前无可用工具。")
    preview = ", ".join(names[:24])
    suffix = f" … (+{len(names) - 24})" if len(names) > 24 else ""
    return SlashCommandOutcome(
        handled=True,
        reply=f"{MONITOR_PREFIX} · 可用工具 ({len(names)}): {preview}{suffix}",
    )


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
    "commands": _cmd_commands,
    "new": _cmd_new,
    "stop": _cmd_stop,
    "status": _cmd_status,
    "sessions": _cmd_sessions,
    "title": _cmd_title,
    "resume": _cmd_resume,
    "skills": _cmd_skills,
    "history": _cmd_history,
    "compress": _cmd_compress,
    "model": _cmd_model,
    "tools": _cmd_tools,
    "retry": _cmd_retry,
    "undo": _cmd_undo,
}
