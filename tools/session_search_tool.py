"""Hermes-aligned session_search tool (FTS5 + fallback browse)."""

from __future__ import annotations

import json

from evolux_constants import get_evolux_home
from evolux_state import SessionDB
from tools.registry import registry


def session_search(
    *,
    query: str | None = None,
    assistant_id: str | None = None,
    limit: int = 20,
) -> str:
    db = SessionDB(home=get_evolux_home())
    try:
        if query and query.strip():
            fts_hits = db.search_messages_fts(
                query.strip(),
                assistant_id=assistant_id,
                limit=limit,
            )
            if fts_hits:
                results = []
                seen: set[tuple[str, str]] = set()
                for hit in fts_hits:
                    key = (str(hit["session_id"]), str(hit["content"])[:80])
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        {
                            "session_id": hit["session_id"],
                            "session_key": hit["session_key"],
                            "assistant_id": hit["assistant_id"],
                            "platform": hit["platform"],
                            "title": hit.get("title") or "",
                            "role": hit["role"],
                            "snippet": str(hit["content"])[:240],
                            "created_at": hit.get("created_at"),
                            "match_source": "fts5",
                        }
                    )
                    if len(results) >= limit:
                        break
                return json.dumps(
                    {
                        "success": True,
                        "mode": "search",
                        "query": query,
                        "results": results,
                        "count": len(results),
                    },
                    ensure_ascii=False,
                )

        sessions = db.list_sessions(assistant_id=assistant_id, limit=100)
        results = []
        needle = (query or "").lower()
        for item in sessions:
            session_id = item["session_id"]
            messages = db.get_messages(session_id)
            preview = ""
            for msg in messages[-3:]:
                preview += f"{msg['role']}: {msg['content'][:120]}\n"
            haystack = f"{item['session_key']} {item.get('title') or ''} {preview}".lower()
            if needle and needle not in haystack:
                continue
            results.append(
                {
                    "session_id": session_id,
                    "session_key": item["session_key"],
                    "assistant_id": item["assistant_id"],
                    "platform": item["platform"],
                    "title": item.get("title") or "",
                    "message_count": item.get("message_count", len(messages)),
                    "preview": preview.strip(),
                    "match_source": "browse",
                }
            )
            if len(results) >= limit:
                break
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
    finally:
        db.close()


SESSION_SEARCH_SCHEMA = {
    "name": "session_search",
    "description": "Search sessions via FTS5 or browse recent sessions (Hermes-compatible).",
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
