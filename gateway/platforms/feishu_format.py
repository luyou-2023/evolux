"""Structured Feishu message builders for orchestrator replies."""

from __future__ import annotations

import json
from typing import Any

from agent.turn_trace import TurnTrace

_CATEGORY_EMOJI = {
    "orchestrator": "🎯",
    "subagent": "🤖",
    "mcp": "🔌",
    "builtin": "🛠",
}


def build_feishu_post_content(*, answer: str, trace: TurnTrace | None = None) -> dict[str, Any]:
    """Build Feishu post msg content (zh_cn) with optional orchestration trace."""
    rows: list[list[dict[str, Any]]] = []

    if trace and (trace.routing_skills or trace.routing_agents or trace.steps):
        rows.append([{"tag": "text", "text": "📋 协调过程\n", "style": ["bold"]}])
        if trace.routing_skills:
            rows.append([{"tag": "text", "text": f"Skill: {', '.join(trace.routing_skills)}\n"}])
        if trace.routing_agents:
            rows.append([{"tag": "text", "text": f"子 Agent: {', '.join(trace.routing_agents)}\n"}])
        for step in trace.steps[:12]:
            emoji = _CATEGORY_EMOJI.get(step.category, "•")
            rows.append([{"tag": "text", "text": f"{emoji} {step.title}\n"}])
            if step.detail and step.category == "subagent":
                rows.append([{"tag": "text", "text": f"   {step.detail[:120]}\n"}])
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


def build_feishu_post_reply(chat_id: str, *, answer: str, trace: TurnTrace | None = None) -> dict[str, Any]:
    return {
        "receive_id": chat_id,
        "msg_type": "post",
        "content": json.dumps(build_feishu_post_content(answer=answer, trace=trace), ensure_ascii=False),
    }


def render_trace_plain(trace: TurnTrace) -> str:
    """Fallback plain-text trace for clients without post support."""
    lines: list[str] = []
    if trace.routing_skills:
        lines.append(f"[Skill] {', '.join(trace.routing_skills)}")
    if trace.routing_agents:
        lines.append(f"[子Agent] {', '.join(trace.routing_agents)}")
    for step in trace.steps[:12]:
        lines.append(f"• {step.title}")
    return "\n".join(lines)


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + limit])
        start += limit
    return chunks
