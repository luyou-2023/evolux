"""Minimal ACP session state for Evolux."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from evolux_constants import get_evolux_home
from gateway.session import SessionSource, build_session_key
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

    def create_session(self, *, cwd: str) -> AcpSessionState:
        session_id = str(uuid.uuid4())
        session_key = build_session_key(
            "default",
            SessionSource(platform="acp", chat_type="dm", chat_id=session_id),
        )
        agent = EvoluxAgent(
            llm_call=self.llm_call,
            home=self.base,
            assistant_id="default",
            settings=self.settings,
        )
        state = AcpSessionState(
            session_id=session_id,
            cwd=str(Path(cwd).expanduser()),
            session_key=session_key,
            agent=agent,
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> AcpSessionState | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        state = self._sessions.pop(session_id, None)
        if state:
            state.agent.close()
