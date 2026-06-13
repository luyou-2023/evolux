"""Persist session compression with parent_session_id chain rotation."""

from __future__ import annotations

from typing import Any

from agent.context_compressor import CompressionResult
from evolux_state import SessionDB


def persist_session_compression(
    db: SessionDB,
    *,
    session_key: str,
    result: CompressionResult,
) -> str | None:
    """Rotate session tip through compression chain; return new session_id."""
    if not result.compressed or not result.summary:
        return None
    tip_id = db.get_session_id_by_key(session_key)
    if not tip_id:
        return None
    row = db.get_session_row_by_id(tip_id)
    if row is None:
        return None
    before_count = db.count_messages(tip_id)
    child_id = db.rotate_session_tip(
        session_key=session_key,
        assistant_id=str(row["assistant_id"]),
        platform=str(row["platform"]),
        parent_session_id=tip_id,
        title=str(row.get("title") or ""),
    )
    db.replace_messages(child_id, result.messages)
    db.log_compression(
        parent_session_id=tip_id,
        child_session_id=child_id,
        summary=result.summary,
        messages_before=before_count,
        messages_after=len(result.messages),
    )
    return child_id
