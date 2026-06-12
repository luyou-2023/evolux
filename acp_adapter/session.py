"""ACP session persistence and MCP passthrough for editor integration."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.runtime import bootstrap, create_llm_call
from evolux_constants import get_evolux_home
from gateway.session import SessionSource, build_session_key
from mcp.registry_bridge import sync_mcp_tools
from run_agent import EvoluxAgent


@dataclass
class AcpSessionState:
    session_id: str
    cwd: str
    session_key: str
    agent: EvoluxAgent


class AcpSessionManager:
    def __init__(self) -> None:
        self.home = get_evolux_home()
        self.base, self.settings = bootstrap(self.home)
        self.llm_call = create_llm_call(self.base, self.settings)
        self._sessions: dict[str, AcpSessionState] = {}
        self._index_path = self.base / "acp" / "sessions.json"
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

    def create_session(self, *, cwd: str, mcp_servers: list[Any] | None = None) -> AcpSessionState:
        session_id = str(uuid.uuid4())
        state = self._build_session(session_id=session_id, cwd=cwd, mcp_servers=mcp_servers)
        self._sessions[session_id] = state
        self._persist_index()
        return state

    def load_session(
        self,
        session_id: str,
        *,
        cwd: str,
        mcp_servers: list[Any] | None = None,
    ) -> AcpSessionState | None:
        existing = self._sessions.get(session_id)
        if existing:
            if mcp_servers:
                apply_session_mcp_servers(existing.agent, mcp_servers)
            return existing

        meta = self._read_index().get(session_id)
        if not meta:
            return None

        state = self._build_session(
            session_id=session_id,
            cwd=cwd or meta.get("cwd", str(self.base)),
            session_key=meta.get("session_key"),
            mcp_servers=mcp_servers,
        )
        self._sessions[session_id] = state
        return state

    def fork_session(
        self,
        parent_session_id: str,
        *,
        cwd: str,
        mcp_servers: list[Any] | None = None,
    ) -> AcpSessionState | None:
        parent = self.get_session(parent_session_id) or self.load_session(
            parent_session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
        )
        if parent is None:
            return None

        child_id = str(uuid.uuid4())
        child = self._build_session(session_id=child_id, cwd=cwd, mcp_servers=mcp_servers)
        self._copy_session_history(parent, child)
        self._sessions[child_id] = child
        self._persist_index()
        return child

    def resume_session(
        self,
        session_id: str,
        *,
        cwd: str,
        mcp_servers: list[Any] | None = None,
    ) -> AcpSessionState | None:
        return self.load_session(session_id, cwd=cwd, mcp_servers=mcp_servers)

    def list_session_ids(self) -> list[str]:
        ids = set(self._read_index().keys()) | set(self._sessions.keys())
        return sorted(ids)

    def get_session(self, session_id: str) -> AcpSessionState | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        state = self._sessions.pop(session_id, None)
        if state:
            state.agent.close()
        index = self._read_index()
        if session_id in index:
            index.pop(session_id, None)
            self._write_index(index)

    def _build_session(
        self,
        *,
        session_id: str,
        cwd: str,
        session_key: str | None = None,
        mcp_servers: list[Any] | None = None,
    ) -> AcpSessionState:
        resolved_key = session_key or build_session_key(
            "default",
            SessionSource(platform="acp", chat_type="dm", chat_id=session_id),
        )
        agent = EvoluxAgent(
            llm_call=self.llm_call,
            home=self.base,
            assistant_id="default",
            settings=self.settings,
        )
        if mcp_servers:
            apply_session_mcp_servers(agent, mcp_servers)
        return AcpSessionState(
            session_id=session_id,
            cwd=str(Path(cwd).expanduser()),
            session_key=resolved_key,
            agent=agent,
        )

    def _copy_session_history(self, parent: AcpSessionState, child: AcpSessionState) -> None:
        parent_db = parent.agent.session_db
        parent_session_id = parent_db.get_session_id_by_key(parent.session_key)
        if not parent_session_id:
            return
        messages = parent_db.get_messages(parent_session_id)
        child_session_id = child.agent.session_db.get_or_create_session(
            session_key=child.session_key,
            assistant_id=child.agent.assistant_id,
            platform="acp",
        )
        for message in messages:
            child.agent.session_db.append_message(
                child_session_id,
                message["role"],
                message["content"],
            )

    def _read_index(self) -> dict[str, dict[str, str]]:
        if not self._index_path.exists():
            return {}
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_index(self, payload: dict[str, dict[str, str]]) -> None:
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _persist_index(self) -> None:
        payload = {
            session_id: {
                "session_key": state.session_key,
                "cwd": state.cwd,
            }
            for session_id, state in self._sessions.items()
        }
        self._write_index(payload)


def apply_session_mcp_servers(agent: EvoluxAgent, mcp_servers: list[Any]) -> list[str]:
    """Register MCP servers supplied by an ACP client for a single session."""
    registered: list[str] = []
    for index, spec in enumerate(mcp_servers):
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name") or f"acp-{index}")
        if spec.get("command"):
            agent.mcp_manager.register_server(
                name,
                {
                    "command": spec["command"],
                    "args": list(spec.get("args") or []),
                    "enabled": True,
                },
            )
        elif spec.get("url"):
            agent.mcp_manager.register_server(
                name,
                {
                    "url": spec["url"],
                    "enabled": True,
                },
            )
        else:
            continue
        sync_mcp_tools(agent.mcp_manager, name)
        registered.append(name)
    return registered
