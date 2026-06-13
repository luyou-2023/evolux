"""Structured Feishu message builders for orchestrator replies."""

from __future__ import annotations

import json
from typing import Any

from agent.turn_trace import TurnTrace, format_coordination_summary

def build_feishu_post_content(*, answer: str, trace: TurnTrace | None = None) -> dict[str, Any]:
    """Build Feishu post msg content (zh_cn) with optional orchestration trace."""
    rows: list[list[dict[str, Any]]] = []

    summary_lines = format_coordination_summary(trace) if trace else []
    if summary_lines:
        rows.append([{"tag": "text", "text": "📋 协调过程\n", "style": ["bold"]}])
        for line in summary_lines:
            rows.append([{"tag": "text", "text": f"{line}\n"}])
        rows.append([{"tag": "text", "text": "\n"}])

    rows.append([{"tag": "text", "text": "💬 回复\n", "style": ["bold"]}])
    for chunk in _split_text(answer or "(无回复)", 1800):
        rows.append([{"tag": "text", "text": chunk}])

    return {
        "zh_cn": {
            "title": "Evolux",
            "content": rows,
        }
    }


def render_trace_plain(trace: TurnTrace) -> str:
    """Fallback plain-text trace for clients without post support."""
    return "\n".join(format_coordination_summary(trace))


def find_clarify_request(trace: TurnTrace | None) -> dict[str, Any] | None:
    if trace is None:
        return None
    for step in reversed(trace.steps):
        if step.name != "clarify":
            continue
        try:
            payload = json.loads(step.detail)
        except json.JSONDecodeError:
            continue
        if payload.get("clarify") and payload.get("question"):
            return payload
    return None


def build_feishu_clarify_card(clarify: dict[str, Any]) -> dict[str, Any]:
    question = str(clarify.get("question") or "")
    options = [str(item) for item in (clarify.get("options") or [])][:6]
    elements: list[dict[str, Any]] = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"**{question}**"}},
    ]
    if options:
        elements.append({"tag": "hr"})
        option_lines = "\n".join(f"{index}. {label}" for index, label in enumerate(options, 1))
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": option_lines}})
        buttons = []
        for label in options[:3]:
            buttons.append(
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": label[:20]},
                    "type": "default",
                    "value": {"action": "clarify", "option": label, "question": question[:100]},
                }
            )
        if buttons:
            elements.append({"tag": "action", "actions": buttons})
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "需要您的确认"},
        },
        "elements": elements,
    }


def build_clarify_selected_card(*, question: str, option: str) -> dict[str, Any]:
    """Card body returned after user clicks a clarify option (replaces interactive buttons)."""
    q = question.strip() or "确认"
    label = option.strip() or "已选择"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green",
            "title": {"tag": "plain_text", "content": "已确认"},
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{q}**"}},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"✅ 您选择了：**{label}**"}},
        ],
    }


def build_feishu_commands_card() -> dict[str, Any]:
    """Interactive card listing Hermes-compatible slash commands for Feishu users."""
    command_lines = [
        ("会话", ["/new", "/stop", "/status", "/sessions", "/title", "/resume", "/history", "/compress", "/retry", "/undo"]),
        ("信息", ["/help", "/commands", "/model", "/tools", "/skills browse"]),
    ]
    elements: list[dict[str, Any]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "在聊天中发送以下 **slash 命令**，由 Session Monitor 即时处理（无需等待 Agent 回复）。",
            },
        },
        {"tag": "hr"},
    ]
    for section, commands in command_lines:
        lines = "\n".join(f"`{cmd}`" for cmd in commands)
        elements.append(
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{section}**\n{lines}"},
            }
        )
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "turquoise",
            "title": {"tag": "plain_text", "content": "Evolux 命令参考"},
        },
        "elements": elements,
    }


def build_feishu_post_reply(chat_id: str, *, answer: str, trace: TurnTrace | None = None) -> dict[str, Any]:
    return {
        "receive_id": chat_id,
        "msg_type": "post",
        "content": json.dumps(build_feishu_post_content(answer=answer, trace=trace), ensure_ascii=False),
    }


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks
