"""Gateway session key construction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionSource:
    platform: str
    chat_type: str = "dm"
    chat_id: str = ""
    user_id: str | None = None
    user_id_alt: str | None = None
    thread_id: str | None = None


def build_session_key(
    assistant_id: str,
    source: SessionSource,
    *,
    group_sessions_per_user: bool = True,
) -> str:
    """Build orchestrator session key with assistant isolation."""
    parts = ["orchestrator", assistant_id, source.platform, source.chat_type]

    if source.chat_type == "dm":
        if source.chat_id:
            parts.append(source.chat_id)
        if source.thread_id:
            parts.append(source.thread_id)
        participant = source.user_id_alt or source.user_id
        if participant:
            parts.append(str(participant))
        return ":".join(parts)

    if source.chat_id:
        parts.append(source.chat_id)
    if source.thread_id:
        parts.append(source.thread_id)
    participant = source.user_id_alt or source.user_id
    if group_sessions_per_user and participant:
        parts.append(str(participant))
    return ":".join(parts)
