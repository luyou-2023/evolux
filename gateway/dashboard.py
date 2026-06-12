"""Simple web dashboard for assistants and sessions."""

from __future__ import annotations

import asyncio
import html
import json
from pathlib import Path
from urllib.parse import quote

from evolux_state import SessionDB
from gateway.activity import get_activity_bus
from gateway.assistant_registry import AssistantRegistry

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment,misc]
    AIOHTTP_AVAILABLE = False


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} · Evolux</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; color: #111; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 0.6rem 0.4rem; text-align: left; vertical-align: top; }}
    th {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: #6b7280; }}
    .nav {{ margin-bottom: 1.5rem; }}
    .nav a {{ margin-right: 1rem; }}
    .badge {{ display: inline-block; background: #eff6ff; color: #1d4ed8; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.8rem; }}
    .msg {{ border-left: 3px solid #dbeafe; padding: 0.5rem 0.75rem; margin: 0.5rem 0; background: #f8fafc; }}
    .role {{ font-weight: 600; color: #374151; }}
    .feed {{ max-height: 70vh; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 0.5rem; padding: 0.5rem; background: #fafafa; }}
    .event {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; padding: 0.45rem 0.6rem; border-bottom: 1px solid #eee; }}
    .event-kind {{ color: #7c3aed; font-weight: 600; }}
    .event-kind-card {{ color: #059669; }}
    .event-kind-progress {{ color: #2563eb; }}
    .event-meta {{ color: #6b7280; font-size: 0.8rem; }}
    .status {{ color: #059669; font-size: 0.9rem; margin-bottom: 0.75rem; }}
  </style>
</head>
<body>
  <div class="nav">
    <a href="/dashboard">Overview</a>
    <a href="/dashboard/assistants">Assistants</a>
    <a href="/dashboard/sessions">Sessions</a>
    <a href="/dashboard/activity">Activity</a>
    <a href="/health">Health</a>
  </div>
  {body}
</body>
</html>"""


def register_dashboard_routes(app: "web.Application", home: Path) -> None:
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for dashboard")

    async def overview(_request: web.Request) -> web.Response:
        registry = AssistantRegistry(home=home)
        db = SessionDB(home=home)
        assistants = registry.list()
        sessions = db.list_sessions(limit=10)
        db.close()
        body = f"""
        <h1>Evolux Dashboard</h1>
        <p>Home: <code>{html.escape(str(home))}</code></p>
        <p><span class="badge">{len(assistants)} assistants</span>
           <span class="badge">{len(sessions)} recent sessions</span></p>
        <h2>Recent Sessions</h2>
        {_sessions_table(sessions)}
        """
        return web.Response(text=_page("Overview", body), content_type="text/html")

    async def assistants(_request: web.Request) -> web.Response:
        registry = AssistantRegistry(home=home)
        rows = []
        for item in registry.list():
            platforms = ", ".join(item.platforms.keys()) or "-"
            rows.append(
                f"<tr><td>{html.escape(item.assistant_id)}</td>"
                f"<td>{html.escape(item.name)}</td>"
                f"<td>{html.escape(platforms)}</td></tr>"
            )
        body = f"""
        <h1>Assistants</h1>
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Platforms</th></tr></thead>
          <tbody>{''.join(rows) or '<tr><td colspan="3">No assistants</td></tr>'}</tbody>
        </table>
        """
        return web.Response(text=_page("Assistants", body), content_type="text/html")

    async def sessions(request: web.Request) -> web.Response:
        assistant_id = request.query.get("assistant_id")
        db = SessionDB(home=home)
        items = db.list_sessions(assistant_id=assistant_id or None, limit=100)
        db.close()
        filter_note = f" (assistant={html.escape(assistant_id)})" if assistant_id else ""
        body = f"""
        <h1>Sessions{filter_note}</h1>
        {_sessions_table(items, link_sessions=True)}
        """
        return web.Response(text=_page("Sessions", body), content_type="text/html")

    async def session_detail(request: web.Request) -> web.Response:
        session_key = request.match_info["session_key"]
        db = SessionDB(home=home)
        session_id = db.get_session_id_by_key(session_key)
        if not session_id:
            db.close()
            return web.Response(text=_page("Not Found", "<h1>Session not found</h1>"), status=404, content_type="text/html")
        messages = db.get_messages(session_id)
        db.close()
        blocks = []
        for msg in messages:
            blocks.append(
                f'<div class="msg"><div class="role">{html.escape(msg["role"])}</div>'
                f'<div>{html.escape(msg["content"])}</div></div>'
            )
        body = f"""
        <h1>Session</h1>
        <p><code>{html.escape(session_key)}</code></p>
        {''.join(blocks) or '<p>No messages yet.</p>'}
        """
        return web.Response(text=_page("Session", body), content_type="text/html")

    async def activity(request: web.Request) -> web.Response:
        session_key = request.query.get("session_key", "")
        events_url = "/dashboard/events"
        if session_key:
            events_url = f"/dashboard/events?session_key={quote(session_key, safe='')}"
        filter_note = (
            f'<p>Filter: <code>{html.escape(session_key)}</code></p>' if session_key else ""
        )
        body = (
            """
        <h1>Live Activity</h1>
        <p class="status" id="status">Connecting…</p>
        """
            + filter_note
            + """
        <div class="feed" id="feed"></div>
        <script>
          const feed = document.getElementById("feed");
          const status = document.getElementById("status");
          const source = new EventSource("""
            + json.dumps(events_url)
            + """);
          function renderEvent(raw) {
            const item = document.createElement("div");
            item.className = "event";
            const kind = document.createElement("span");
            kind.className = "event-kind" + (
              raw.kind === "card_action_received" ? " event-kind-card"
              : raw.kind === "progress_update" ? " event-kind-progress"
              : ""
            );
            kind.textContent = raw.kind || "event";
            const meta = document.createElement("div");
            meta.className = "event-meta";
            const parts = [];
            if (raw.platform) parts.push(raw.platform);
            if (raw.session_key) parts.push(raw.session_key);
            if (raw.tool) parts.push("tool=" + raw.tool);
            if (raw.detail) parts.push(raw.detail);
            meta.textContent = parts.join(" · ");
            item.appendChild(kind);
            item.appendChild(meta);
            feed.prepend(item);
            while (feed.children.length > 200) feed.removeChild(feed.lastChild);
          }
          source.onopen = () => { status.textContent = "Connected"; };
          source.onerror = () => { status.textContent = "Disconnected — retrying…"; };
          source.onmessage = (event) => {
            try { renderEvent(JSON.parse(event.data)); } catch (_) {}
          };
        </script>
        """
        )
        return web.Response(text=_page("Activity", body), content_type="text/html")

    async def events(request: web.Request) -> web.StreamResponse:
        bus = get_activity_bus()
        queue = bus.subscribe()
        session_filter = request.query.get("session_key") or None
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)
        for event in bus.recent(30):
            if session_filter and event.session_key != session_filter:
                continue
            await response.write(f"data: {event.to_json()}\n\n".encode("utf-8"))
        if request.query.get("once") == "1":
            return response
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if session_filter and item.session_key != session_filter:
                    continue
                await response.write(f"data: {item.to_json()}\n\n".encode("utf-8"))
        finally:
            bus.unsubscribe(queue)
        return response

    app.router.add_get("/dashboard", overview)
    app.router.add_get("/dashboard/", overview)
    app.router.add_get("/dashboard/assistants", assistants)
    app.router.add_get("/dashboard/sessions", sessions)
    app.router.add_get("/dashboard/sessions/{session_key:.+}", session_detail)
    app.router.add_get("/dashboard/activity", activity)
    app.router.add_get("/dashboard/events", events)


def _sessions_table(sessions: list[dict], *, link_sessions: bool = False) -> str:
    rows = []
    for item in sessions:
        key = str(item.get("session_key", ""))
        key_cell = html.escape(key)
        if link_sessions:
            key_cell = f'<a href="/dashboard/sessions/{quote(key, safe="")}">{key_cell}</a>'
        rows.append(
            f"<tr><td>{key_cell}</td>"
            f"<td>{html.escape(str(item.get('assistant_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('platform', '')))}</td>"
            f"<td>{item.get('message_count', 0)}</td>"
            f"<td>{html.escape(str(item.get('created_at', '')))}</td></tr>"
        )
    return f"""
    <table>
      <thead><tr><th>Session Key</th><th>Assistant</th><th>Platform</th><th>Messages</th><th>Created</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="5">No sessions</td></tr>'}</tbody>
    </table>
    """
