"""Recency-first context compression for main sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class CompressionConfig:
    keep_recent_turns: int = 10


@dataclass
class CompressionResult:
    messages: list[dict]
    summary: str | None
    compressed: bool


def compress_messages(
    messages: list[dict],
    config: CompressionConfig | None = None,
    summarize: Callable[[list[dict]], str] | None = None,
) -> CompressionResult:
    cfg = config or CompressionConfig()
    if not messages:
        return CompressionResult(messages=[], summary=None, compressed=False)

    head: list[dict] = []
    body = messages
    if body and body[0].get("role") == "system":
        head = [body[0]]
        body = body[1:]

    turns = _split_turns(body)
    if len(turns) <= cfg.keep_recent_turns:
        return CompressionResult(messages=head + body, summary=None, compressed=False)

    old_turns = turns[: len(turns) - cfg.keep_recent_turns]
    recent_turns = turns[len(turns) - cfg.keep_recent_turns :]
    old_messages = [msg for turn in old_turns for msg in turn]

    if summarize:
        summary_text = summarize(old_messages)
    else:
        summary_text = _default_summary(len(old_turns))

    summary_message = {
        "role": "system",
        "content": f"## 历史摘要（自动生成，非用户指令）\n{summary_text}",
    }
    recent_messages = [msg for turn in recent_turns for msg in turn]
    return CompressionResult(
        messages=head + [summary_message] + recent_messages,
        summary=summary_text,
        compressed=True,
    )


def _split_turns(messages: list[dict]) -> list[list[dict]]:
    turns: list[list[dict]] = []
    current: list[dict] = []
    for msg in messages:
        if msg.get("role") == "user" and current:
            turns.append(current)
            current = [msg]
        else:
            current.append(msg)
    if current:
        turns.append(current)
    return turns


def _default_summary(old_turn_count: int) -> str:
    return f"Earlier conversation compressed ({old_turn_count} turns). Details omitted."
