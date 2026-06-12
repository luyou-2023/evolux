"""Hermes-aligned session_search tool (browse + keyword filter)."""

from __future__ import annotations

import json

from evolux_constants import get_evolux_home
from evolux_state import SessionDB
from tools.registry import registry, tool_error


def session_search(
    *,
    query: str | None = None,
    assistant_id: str | None = None,
    limit: int = 20,
) -> str:
    db = SessionDB(home=get_evolux_home())
    sessions = db.list_sessions(assistant_id=assistant_id, limit=100)
    results = []
    for item in sessions:
        session_id = item["session_id"]
        messages = db.get_messages(session_id)
        preview = ""
        for msg in messages[-3:]:
            preview += f"{msg['role']}: {msg['content'][:120]}\n"
        haystack = f"{item['session_key']} {preview}".lower()
        if query and query.lower() not in haystack:
            continue
        results.append(
            {
                "session_id": session_id,
                "session_key": item["session_key"],
                "assistant_id": item["assistant_id"],
                "platform": item["platform"],
                "message_count": item.get("message_count", len(messages)),
                "preview": preview.strip(),
            }
        )
        if len(results) >= limit:
            break
    db.close()
    mode = "search" if query else "recent"
    return json.dumps(
        {
            "success": True,
            "mode": mode,
            "query": query,
            "results": results,
            "count": len(results),
        },
        ensure_ascii=False,
    )


SESSION_SEARCH_SCHEMA = {
    "name": "session_search",
    "description": "Browse recent sessions or filter by keyword (Hermes-compatible subset).",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional keyword filter"},
            "assistant_id": {"type": "string"},
            "limit": {"type": "integer"},
        },
    },
}

registry.register(
    "session_search",
    lambda args, **_: session_search(
        query=args.get("query"),
        assistant_id=args.get("assistant_id"),
        limit=int(args.get("limit", 20)),
    ),
    SESSION_SEARCH_SCHEMA,
    toolset="session_search",
)
